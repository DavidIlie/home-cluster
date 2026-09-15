<?php

namespace N3rdMade\MinecraftConfig;

use Filament\Contracts\Plugin;
use Filament\Panel;

class MinecraftConfigPlugin implements Plugin
{
    public function getId(): string
    {
        return 'minecraft-config';
    }

    public function register(Panel $panel): void
    {
        $id = str($panel->getId())->title();

        $panel->discoverPages(
            plugin_path($this->getId(), "src/Filament/$id/Pages"),
            "N3rdMade\\MinecraftConfig\\Filament\\$id\\Pages"
        );
    }

    public function boot(Panel $panel): void {}
}
