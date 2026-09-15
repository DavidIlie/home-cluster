<?php
namespace DavidApps\Forwarder;
use Filament\Contracts\Plugin;
use Filament\Panel;
use DavidApps\Forwarder\Filament\Pages\PublicAddress;
class ForwarderPlugin implements Plugin
{
    public function getId(): string { return 'davidapps-forwarder'; }
    public function register(Panel $panel): void { $panel->pages([PublicAddress::class]); }
    public function boot(Panel $panel): void {}
}
