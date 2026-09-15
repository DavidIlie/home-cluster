<?php
namespace DavidApps\Appearance\Providers;
use DavidApps\Appearance\ThemePreference;
use Filament\Facades\Filament;
use Filament\Support\Facades\FilamentColor;
use Illuminate\Support\ServiceProvider;
class AppearanceProvider extends ServiceProvider
{
    public function boot(): void {
        Filament::serving(function () {
            $panel = Filament::getCurrentPanel();
            $theme = ThemePreference::current();
            if ($theme === 'hairline') {
                (new \WisdomIT\Hairline\Providers\HairlineProvider($this->app))->boot();
            } elseif ($theme === 'nord') {
                (new \Boy132\NordTheme\NordThemePlugin())->register($panel);
                FilamentColor::register($panel->getColors());
            } elseif ($theme === 'mocha') {
                (new \SteveFrost\CatppuccinMochaTheme\CatppuccinMochaThemePlugin())->register($panel);
                FilamentColor::register($panel->getColors());
            }
        });
    }
}
