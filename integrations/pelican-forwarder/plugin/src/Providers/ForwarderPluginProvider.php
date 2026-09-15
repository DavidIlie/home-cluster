<?php
namespace DavidApps\Forwarder\Providers;
use DavidApps\Forwarder\Services\Forwarder;
use Illuminate\Console\Scheduling\Schedule;
use Illuminate\Support\ServiceProvider;
class ForwarderPluginProvider extends ServiceProvider
{
    public function boot(): void {
        $this->callAfterResolving(Schedule::class, function (Schedule $schedule) {
            $schedule->call(fn () => app(Forwarder::class)->syncAll())->name('davidapps-forwarder')->everyMinute()->withoutOverlapping();
        });
    }
}
