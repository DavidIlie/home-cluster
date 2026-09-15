<?php
namespace DavidApps\Appearance;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\ValidationException;
class ThemePreference
{
    public const OPTIONS = ['mocha' => 'Catppuccin Mocha', 'hairline' => 'Hairline', 'nord' => 'Nord', 'default' => 'Pelican default'];
    public static function current(): string {
        if (!user()) { return 'hairline'; }
        $theme = DB::table('davidapps_theme_preferences')->where('user_id', user()->id)->value('theme');
        return array_key_exists($theme ?? '', self::OPTIONS) ? $theme : 'hairline';
    }
    public static function save(string $theme): void {
        abort_unless(user(), 403);
        if (!array_key_exists($theme, self::OPTIONS)) {
            throw ValidationException::withMessages(['theme' => 'Choose one of the available themes.']);
        }
        DB::table('davidapps_theme_preferences')->updateOrInsert(['user_id' => user()->id], ['theme' => $theme]);
    }
}
