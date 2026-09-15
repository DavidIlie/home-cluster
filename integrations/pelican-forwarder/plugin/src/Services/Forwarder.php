<?php
namespace DavidApps\Forwarder\Services;
use App\Models\Server;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Validation\ValidationException;
use RuntimeException;
class Forwarder
{
    public const TARGET = 'mc-forward.davidapps.dev';
    public function supports(Server $server): bool {
        return $server->node_id === 1 && in_array('minecraft', $server->egg?->tags ?? [], true) && in_array('java_version', $server->egg?->features ?? [], true);
    }
    public function backend(Server $server): string {
        $port = $server->allocation?->port;
        if (!$port || $port < 1024 || $port > 65535) { throw new RuntimeException('No valid primary allocation.'); }
        return '192.168.100.163:' . $port;
    }
    public function request(string $method, array $data = []): array {
        $token = trim(file_get_contents('/etc/pelican-forwarder/token'));
        return Http::withToken($token)->acceptJson()->connectTimeout(3)->timeout(15)
            ->send($method, 'http://192.168.2.5:8091/routes', ['json' => $data])->throw()->json();
    }
    public function address(Server $server): object {
        abort_unless($this->supports($server), 404);
        $legacy = [1 => 'im.gurt.ing', 2 => 'mc.anaxax.tv'];
        DB::table('davidapps_forward_addresses')->insertOrIgnore([
            'server_id' => $server->id, 'server_uuid' => $server->uuid,
            'hostname' => $legacy[$server->id] ?? ($server->uuid_short . '.' . self::TARGET),
            'backend' => $this->backend($server), 'challenge' => bin2hex(random_bytes(24)),
        ]);
        return DB::table('davidapps_forward_addresses')->where('server_id', $server->id)->first();
    }
    public function syncAll(): void {
        Cache::lock('davidapps-forwarder-sync', 300)->get(function () {
            $managedOwners = DB::table('davidapps_forward_addresses')->pluck('server_uuid')->all();
            foreach (Server::with(['egg', 'allocation'])->get() as $server) {
                if (!$this->supports($server)) { continue; }
                $row = $this->address($server);
                try {
                    $backend = $this->backend($server);
                    $this->request('PUT', ['hostname' => $row->hostname, 'owner' => $server->uuid, 'backend' => $backend]);
                    retry(5, function () use ($row, $backend) {
                        $active = $this->request('GET')['active'] ?? [];
                        if (($active[$row->hostname] ?? null) !== $backend) { throw new RuntimeException('Route is not active yet.'); }
                    }, 200);
                    DB::table('davidapps_forward_addresses')->where('id', $row->id)->update(['backend' => $backend, 'error' => null, 'synced_at' => now()]);
                } catch (\Throwable $e) {
                    DB::table('davidapps_forward_addresses')->where('id', $row->id)->update(['error' => 'Relay synchronization failed. It will retry automatically.']);
                    report($e);
                }
            }
            foreach (DB::table('davidapps_forward_addresses')->get() as $row) {
                $server = Server::find($row->server_id);
                if ($server && $this->supports($server)) { continue; }
                try {
                    $this->request('DELETE', ['hostname' => $row->hostname, 'owner' => $row->server_uuid, 'backend' => $row->backend]);
                    DB::table('davidapps_forward_addresses')->where('id', $row->id)->delete();
                } catch (\Throwable $e) { report($e); }
            }
            try {
                $desired = DB::table('davidapps_forward_addresses')->pluck('hostname')->all();
                $routes = $this->request('GET');
                foreach ($routes['owners'] as $host => $owner) {
                    if (in_array($owner, $managedOwners, true) && !in_array($host, $desired, true)) {
                        $this->request('DELETE', ['hostname' => $host, 'owner' => $owner, 'backend' => $routes['mappings'][$host]]);
                    }
                }
            } catch (\Throwable $e) { report($e); }
        });
    }
    public function dns(string $host): bool {
        $addresses = @dns_get_record($host, DNS_A) ?: [];
        $target = array_column(@dns_get_record(self::TARGET, DNS_A) ?: [], 'ip');
        $actual = array_column($addresses, 'ip');
        return count($actual) > 0 && count(array_diff($actual, $target)) === 0 && count(@dns_get_record($host, DNS_AAAA) ?: []) === 0;
    }
    public function change(Server $server, string $hostname): void {
        $hostname = strtolower(rtrim(trim($hostname), '.'));
        if (strlen($hostname) > 253 || !preg_match('/^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/D', $hostname)) {
            throw ValidationException::withMessages(['hostname' => 'Enter a full domain name without a port.']);
        }
        Cache::lock('davidapps-forwarder-sync', 120)->block(5, function () use ($server, $hostname) {
            $row = $this->address($server);
            if ($hostname === $row->hostname) { return; }
            $proof = array_column(@dns_get_record('_pelican.' . $hostname, DNS_TXT) ?: [], 'txt');
            if (!in_array($row->challenge, $proof, true)) {
                throw ValidationException::withMessages(['hostname' => 'Add the TXT ownership record shown below, then try again.']);
            }
            if (DB::table('davidapps_forward_addresses')->where('hostname', $hostname)->exists()) {
                throw ValidationException::withMessages(['hostname' => 'This hostname is already assigned.']);
            }
            $backend = $this->backend($server);
            $this->request('PUT', ['hostname' => $hostname, 'owner' => $server->uuid, 'backend' => $backend]);
            DB::table('davidapps_forward_addresses')->where('id', $row->id)->update(['hostname' => $hostname, 'backend' => $backend, 'synced_at' => now(), 'error' => null]);
            $this->request('DELETE', ['hostname' => $row->hostname, 'owner' => $server->uuid, 'backend' => $row->backend]);
        });
    }
}
