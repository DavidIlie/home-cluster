<?php
namespace DavidApps\Forwarder\Filament\Pages;
use App\Models\Server;
use DavidApps\Forwarder\Services\Forwarder;
use Filament\Facades\Filament;
use Filament\Notifications\Notification;
use Filament\Pages\Page;
class PublicAddress extends Page
{
    protected static string|\BackedEnum|null $navigationIcon = 'tabler-world-www';
    protected static ?string $navigationLabel = 'Public address';
    protected static ?int $navigationSort = 12;
    protected string $view = 'davidapps-forwarder::public-address';
    public string $hostname = '';
    public static function canAccess(): bool {
        $server = Filament::getTenant();
        return $server instanceof Server && app(Forwarder::class)->supports($server);
    }
    public function mount(): void {
        abort_unless(static::canAccess(), 403);
        $this->hostname = app(Forwarder::class)->address(Filament::getTenant())->hostname;
    }
    public function canEdit(): bool {
        return user()?->isRootAdmin() || user()?->id === Filament::getTenant()?->owner_id;
    }
    public function save(): void {
        abort_unless(static::canAccess() && $this->canEdit(), 403);
        try {
            app(Forwarder::class)->change(Filament::getTenant(), $this->hostname);
            Notification::make()->title('Public address updated')->success()->send();
        } catch (\Illuminate\Validation\ValidationException $e) { throw $e;
        } catch (\Throwable $e) {
            report($e);
            Notification::make()->title('Could not synchronize with the relay. Try again shortly.')->danger()->send();
        }
    }
    protected function getViewData(): array {
        $service = app(Forwarder::class);
        $row = $service->address(Filament::getTenant());
        return ['address' => $row, 'dnsReady' => $service->dns($row->hostname), 'target' => Forwarder::TARGET];
    }
}
