<?php
require '/var/www/html/vendor/autoload.php';
$app = require '/var/www/html/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use James\CoolPlugin\Console\Commands\CollectPlayerCounts;
use James\CoolPlugin\Console\Commands\ScanLogs;
use James\CoolPlugin\Models\PlayerEvent;
function check($ok, $label) { if (!$ok) { throw new RuntimeException($label); } echo "PASS: $label\n"; }
$server = App\Models\Server::findOrFail(1);
$headers = ['User-Agent' => 'Pelican Wings/v1.0.0 (id:'.$server->node->daemon_token_id.')'];
DB::beginTransaction();
try {
    PlayerEvent::where('server_id', $server->id)->delete();
    PlayerEvent::recordEvent($server->id, 'test-player', 'join', now()->subMinute()->format('Y-m-d H:i:s'));
    $method = new ReflectionMethod(CollectPlayerCounts::class, 'getPlayerCount');
    Http::fake(['*' => Http::sequence()->push(['state' => 'offline'], 200, $headers)->push(['state' => 'running'], 200, $headers)->push(['state' => 'missing'], 200, $headers)->push(['state' => 'offline'], 200, $headers)]);
    foreach (['offline' => 0, 'running' => 1, 'missing' => -1] as $state => $expected) {
        check($method->invoke(new CollectPlayerCounts(), $server) === $expected, "$state state handled correctly");
    }
    $scan = new ReflectionMethod(ScanLogs::class, 'scanServer');
    check($scan->invoke(new ScanLogs(), $server) === 0, 'stopped server logs are not imported as current activity');
    $settings = (new James\CoolPlugin\CoolPluginPlugin())->getSettingsFormData();
    check(isset($settings['widget_position']), 'panel settings interface supported');
} finally {
    DB::rollBack();
}
