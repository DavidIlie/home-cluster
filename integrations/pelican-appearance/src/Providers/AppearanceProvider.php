<?php
namespace DavidApps\Appearance\Providers;
use DavidApps\Appearance\ThemePreference;
use Filament\Facades\Filament;
use Filament\Support\Facades\FilamentColor;
use Filament\Support\Facades\FilamentView;
use Illuminate\Support\ServiceProvider;
class AppearanceProvider extends ServiceProvider
{
    public function boot(): void {
        $this->app->register(\PhantomVoidTTV\VoidwaveTheme\Providers\VoidwaveRoutesProvider::class);
        Filament::serving(function () {
            $panel = Filament::getCurrentPanel();
            $theme = ThemePreference::current();
            if ($theme === 'hairline') {
                (new \WisdomIT\Hairline\Providers\HairlineProvider($this->app))->boot();
                return;
            }
            $themes = [
                'nord' => \Boy132\NordTheme\NordThemePlugin::class,
                'mocha' => \SteveFrost\CatppuccinMochaTheme\CatppuccinMochaThemePlugin::class,
                'deepfield' => \Gurvinny\Deepfield\DeepfieldPlugin::class,
                'voidwave' => \PhantomVoidTTV\VoidwaveTheme\VoidwaveThemePlugin::class,
                'starrynight' => \JoanFo\StarryNight\StarryNightPlugin::class,
                'neobrutalism' => \Boy132\NeobrutalismTheme\NeobrutalismThemePlugin::class,
                'fluffy' => \Boy132\FluffyTheme\FluffyThemePlugin::class,
            ];
            if (!isset($themes[$theme])) { return; }
            if ($theme === 'deepfield') {
                $this->app->register(\Gurvinny\Deepfield\Providers\DeepfieldPluginProvider::class);
            } elseif ($theme === 'starrynight') {
                $this->app->register(\JoanFo\StarryNight\Providers\StarryNightPluginProvider::class);
            } elseif ($theme === 'voidwave') {
                $this->app->register(\PhantomVoidTTV\VoidwaveTheme\Providers\VoidwaveProfileProvider::class);
            }
            $property = new \ReflectionProperty($panel, 'renderHooks');
            $before = $property->getValue($panel);
            (new $themes[$theme]())->register($panel);
            FilamentColor::register($panel->getColors());
            foreach ($property->getValue($panel) as $name => $scopes) {
                foreach ($scopes as $scope => $hooks) {
                    foreach (array_slice($hooks, count($before[$name][$scope] ?? [])) as $hook) {
                        FilamentView::registerRenderHook($name, $hook, $scope);
                    }
                }
            }
        });
    }
}
