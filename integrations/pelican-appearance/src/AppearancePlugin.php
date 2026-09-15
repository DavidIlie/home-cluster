<?php
namespace DavidApps\Appearance;
use Filament\Actions\Action;
use Filament\Contracts\Plugin;
use Filament\Facades\Filament;
use Filament\Forms\Components\Radio;
use Filament\Panel;
class AppearancePlugin implements Plugin
{
    public function getId(): string { return 'davidapps-appearance'; }
    public function register(Panel $panel): void {
        $panel->userMenuItems([
            Action::make('appearance')
                ->label('Appearance')
                ->icon('tabler-palette')
                ->modalHeading('Choose your theme')
                ->modalDescription('Your choice applies to your account across the panel. Other people keep their own theme.')
                ->modalSubmitActionLabel('Apply theme')
                ->schema([
                    Radio::make('theme')->label('Theme')->options(ThemePreference::OPTIONS)
                        ->descriptions([
                            'mocha' => 'Soft purple accents and dark backgrounds. Dark mode only.',
                            'hairline' => 'Compact spacing and sharp borders. Light and dark modes.',
                            'nord' => 'Cool blue and grey colours. Light and dark modes.',
                            'deepfield' => 'Space backgrounds with violet accents.',
                            'voidwave' => 'Animated cosmic backgrounds. Dark mode only.',
                            'starrynight' => 'Stars and meteors. Light and dark modes.',
                            'neobrutalism' => 'Bold outlines and strong shadows.',
                            'fluffy' => 'Playful handwritten lettering and pastel colours.',
                            'default' => 'The standard Pelican appearance. Light and dark modes.',
                        ])->required(),
                ])
                ->fillForm(fn () => ['theme' => ThemePreference::current()])
                ->action(function (array $data) {
                    ThemePreference::save($data['theme']);
                    return redirect(Filament::getPanel('app')->getUrl());
                }),
        ]);
    }
    public function boot(Panel $panel): void {}
}
