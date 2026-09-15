<?php

namespace N3rdMade\MinecraftConfig\Filament\Server\Pages;

use App\Models\Server;
use App\Repositories\Daemon\DaemonFileRepository;
use App\Traits\Filament\BlockAccessInConflict;
use BackedEnum;
use Exception;
use RuntimeException;
use Filament\Actions\Action;
use Filament\Facades\Filament;
use Filament\Forms\Components\KeyValue;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\Textarea;
use Filament\Forms\Components\TagsInput;
use Filament\Forms\Components\TextInput;
use Filament\Forms\Components\Toggle;
use Filament\Forms\Concerns\InteractsWithForms;
use Filament\Infolists\Components\TextEntry;
use Filament\Notifications\Notification;
use Filament\Pages\Concerns\InteractsWithFormActions;
use Filament\Pages\Page;
use Filament\Schemas\Components\Component;
use Filament\Schemas\Components\Group;
use Filament\Schemas\Components\Section;
use Filament\Schemas\Components\StateCasts\BooleanStateCast;
use Filament\Schemas\Components\Tabs;
use Filament\Schemas\Components\Tabs\Tab;
use Filament\Schemas\Components\Utilities\Get;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;

class MinecraftConfigPage extends Page
{
    use BlockAccessInConflict;
    use InteractsWithFormActions;
    use InteractsWithForms;

    protected static string|BackedEnum|null $navigationIcon = 'tabler-adjustments';

    protected static ?string $slug = 'minecraft-config';

    protected static ?int $navigationSort = 23;

    protected string $view = 'filament.server.pages.server-form-page';

    public ?array $data = [];

    public array $detectedProperties = [];

    public static function canAccess(): bool
    {
        
        $server = Filament::getTenant();

        $eggName = strtolower($server->egg?->name ?? '');
        $isMinecraft = Str::contains($eggName, [
            'minecraft',
            'forge',
            'neoforge',
            'fabric',
            'quilt',
            'paper',
            'purpur',
            'spigot',
            'bukkit',
        ]);

        return parent::canAccess()
            && $isMinecraft
            && $server->owner_id === user()?->id;
    }

    public static function getNavigationLabel(): string
    {
        return 'Minecraft Config';
    }

    public static function getModelLabel(): string
    {
        return 'Minecraft Config';
    }

    public static function getPluralModelLabel(): string
    {
        return 'Minecraft Config';
    }

    public function getTitle(): string
    {
        return 'Minecraft Server Config';
    }

    public function mount(): void
    {
        abort_unless(static::canAccess(), 403);
        
        $server = Filament::getTenant();

        try {
            $raw = $this->readPropertiesFile($server);
            $this->detectedProperties = $this->parseProperties($raw);
        } catch (\Illuminate\Contracts\Filesystem\FileNotFoundException $exception) {
            $this->detectedProperties = [];

            Notification::make()
                ->title('server.properties not found yet')
                ->body('Defaults are shown. Start the server once to generate server.properties, or save here to create it.')
                ->warning()
                ->send();
        }

        $state = $this->makeFormState($this->detectedProperties);
        $state['whitelist_players'] = array_values(array_map(
            fn (array $entry): string => (string) ($entry['name'] ?? ''),
            $this->readWhitelistEntries($server)
        ));
        $state['other_properties'] = $this->unknownProperties();
        $state['code_of_conduct_text'] = $this->readOptionalTextFile($server, 'codeofconduct/en_us.txt');

        $this->form->fill($state);
    }

    protected function getFormSchema(): array
    {
        return [
            Section::make('Server Properties')
                ->description('Friendly controls for server.properties, whitelist.json, and a fallback editor for every other server.properties key.')
                ->compact()
                ->schema([
                    Group::make()
                        ->columns(3)
                        ->schema([
                            TextEntry::make('properties_file')
                                ->label('File')
                                ->state('server.properties')
                                ->badge(),

                            TextEntry::make('known_count')
                                ->label('Managed settings')
                                ->state((string) count($this->definitions()))
                                ->badge()
                                ->color('success'),

                            TextEntry::make('unknown_count')
                                ->label('Other editable settings')
                                ->state((string) count($this->unknownProperties()))
                                ->badge()
                                ->color(count($this->unknownProperties()) > 0 ? 'info' : 'gray'),
                        ]),
                ]),

            Tabs::make('minecraft_settings')
                ->persistTabInQueryString()
                ->tabs([
                    Tab::make('general')
                        ->label('General')
                        ->icon('tabler-home')
                        ->schema($this->generalTab()),

                    Tab::make('gameplay')
                        ->label('Gameplay')
                        ->icon('tabler-device-gamepad-2')
                        ->schema($this->gameplayTab()),

                    Tab::make('whitelist')
                        ->label('Whitelist')
                        ->icon('tabler-user-check')
                        ->schema($this->whitelistTab()),

                    Tab::make('world')
                        ->label('World')
                        ->icon('tabler-world')
                        ->schema($this->worldTab()),

                    Tab::make('network')
                        ->label('Network')
                        ->icon('tabler-network')
                        ->schema($this->networkTab()),

                    Tab::make('rcon_query')
                        ->label('RCON / Query')
                        ->icon('tabler-terminal-2')
                        ->schema($this->rconQueryTab()),

                    Tab::make('performance')
                        ->label('Performance')
                        ->icon('tabler-gauge')
                        ->schema($this->performanceTab()),

                    Tab::make('resource_pack')
                        ->label('Resource Pack')
                        ->icon('tabler-package')
                        ->schema($this->resourcePackTab()),

                    Tab::make('advanced')
                        ->label('Advanced')
                        ->icon('tabler-settings-2')
                        ->schema($this->advancedTab()),
                ]),
        ];
    }

    protected function getFormStatePath(): ?string
    {
        return 'data';
    }

    protected function getHeaderActions(): array
    {
        return [
            Action::make('reload')
                ->label('Reload')
                ->icon('tabler-refresh')
                ->color('gray')
                ->action(fn () => $this->redirect(static::getUrl())),

            Action::make('save')
                ->label('Save')
                ->icon('tabler-device-floppy')
                ->color('primary')
                ->keyBindings(['mod+s'])
                ->action('save'),
        ];
    }

    public function save(): void
    {
        abort_unless(static::canAccess(), 403);
        
        $server = Filament::getTenant();

        try {
            $formData = $this->form->getState();

            try {
                $raw = $this->readPropertiesFile($server);
            } catch (\Illuminate\Contracts\Filesystem\FileNotFoundException) {
                $raw = "#Minecraft server properties\n";
            }

            $current = $this->parseProperties($raw);
            $updates = [];

            foreach ($this->definitions() as $formKey => $definition) {
                $property = $definition['property'];
                $value = $this->serializeValue($formData[$formKey] ?? $definition['default'], $definition['type']);
                $default = $this->serializeValue($definition['default'], $definition['type']);

                if (array_key_exists($property, $current) || $value !== $default) {
                    $updates[$property] = $value;
                }
            }

            $originalOther = $this->unknownPropertiesFrom($current);
            $otherUpdates = $this->sanitizeOtherProperties($formData['other_properties'] ?? []);
            $removedOther = array_values(array_diff(array_keys($originalOther), array_keys($otherUpdates)));
            $updates = array_merge($updates, $otherUpdates);

            $newRaw = $this->applyUpdates($raw, $updates, $removedOther);

            $this->validateSupplementalSettings($formData);

            $wasOnlineMode = filter_var($current['online-mode'] ?? true, FILTER_VALIDATE_BOOLEAN);
            $onlineMode = (bool) ($formData['online_mode'] ?? true);
            $whitelistEntries = $this->buildWhitelistEntries(
                $server,
                $formData['whitelist_players'] ?? [],
                $onlineMode,
                $wasOnlineMode !== $onlineMode
            );

            $this->writeWhitelistEntries($server, $whitelistEntries);
            $this->writeCodeOfConduct($server, $formData);

            $repository = (new DaemonFileRepository())->setServer($server);
            $repository->putContent('server.properties', $newRaw)->throw();

            $liveWhitelistApplied = $this->applyWhitelistLive($server, (bool) ($formData['white_list'] ?? false));
            $this->detectedProperties = $this->parseProperties($newRaw);

            Notification::make()
                ->title('Minecraft settings saved')
                ->body($liveWhitelistApplied
                    ? 'server.properties and whitelist.json were saved. Whitelist changes were also applied to the running server.'
                    : 'server.properties and whitelist.json were saved. Restart the server to apply settings that are not live-reloadable.')
                ->success()
                ->send();

            $this->redirect(static::getUrl());
        } catch (Exception $exception) {
            report($exception);

            Notification::make()
                ->title('Could not save Minecraft settings')
                ->body($exception->getMessage())
                ->danger()
                ->send();
        }
    }

    private function generalTab(): array
    {
        return [
            Section::make('Server Identity')
                ->columns(2)
                ->schema([
                    TextInput::make('motd')
                        ->label('MOTD')
                        ->helperText('The text shown in the Minecraft multiplayer server list.')
                        ->maxLength(512)
                        ->columnSpanFull(),

                    TextInput::make('max_players')
                        ->label('Max Players')
                        ->numeric()
                        ->minValue(1)
                        ->maxValue(1000),

                    TextInput::make('player_idle_timeout')
                        ->label('AFK Kick (minutes)')
                        ->numeric()
                        ->minValue(0)
                        ->helperText('0 disables the idle timeout.'),
                ]),

            Section::make('Common Server Options')
                ->columns(2)
                ->schema([
                    Select::make('gamemode')
                        ->label('Default Game Mode')
                        ->options([
                            'survival' => 'Survival',
                            'creative' => 'Creative',
                            'adventure' => 'Adventure',
                            'spectator' => 'Spectator',
                        ])
                        ->selectablePlaceholder(false),

                    Select::make('difficulty')
                        ->label('Difficulty')
                        ->options([
                            'peaceful' => 'Peaceful',
                            'easy' => 'Easy',
                            'normal' => 'Normal',
                            'hard' => 'Hard',
                        ])
                        ->selectablePlaceholder(false),

                    $this->booleanToggle('online_mode', 'Online Mode', 'Authenticate players with Mojang/Microsoft. Leave enabled for normal public servers.'),
                    $this->booleanToggle('force_gamemode', 'Force Game Mode', 'Force the default game mode when a player joins.'),

                    $this->booleanToggle('hardcore', 'Hardcore', 'Players are placed in spectator mode after dying on modern servers.'),
                    $this->booleanToggle('pvp', 'PvP', 'Allow players to damage each other.'),
                ]),
        ];
    }

    private function gameplayTab(): array
    {
        return [
            Section::make('Players & Commands')
                ->columns(2)
                ->schema([
                    $this->booleanToggle('allow_flight', 'Allow Flight', 'Prevents the server from kicking players for flying when mods or abilities allow it.'),
                    $this->booleanToggle('enable_command_block', 'Command Blocks'),

                    Select::make('op_permission_level')
                        ->label('OP Permission Level')
                        ->options([
                            1 => '1 - Bypass spawn protection',
                            2 => '2 - Most single-player commands',
                            3 => '3 - Player management commands',
                            4 => '4 - Full server control',
                        ])
                        ->selectablePlaceholder(false),

                    Select::make('function_permission_level')
                        ->label('Function Permission Level')
                        ->options([
                            1 => '1',
                            2 => '2',
                            3 => '3',
                            4 => '4',
                        ])
                        ->selectablePlaceholder(false),

                    TextInput::make('spawn_protection')
                        ->label('Spawn Protection Radius')
                        ->numeric()
                        ->minValue(0)
                        ->maxValue(10000),

                    $this->booleanToggle('broadcast_console_to_ops', 'Broadcast Console to OPs'),
                    $this->booleanToggle('broadcast_rcon_to_ops', 'Broadcast RCON to OPs'),
                ]),

            Section::make('Mobs & Dimensions')
                ->columns(2)
                ->schema([
                    $this->booleanToggle('allow_nether', 'Allow Nether'),
                    $this->booleanToggle('spawn_animals', 'Spawn Animals'),
                    $this->booleanToggle('spawn_monsters', 'Spawn Monsters'),
                    $this->booleanToggle('spawn_npcs', 'Spawn NPCs / Villagers'),
                ]),
        ];
    }

    private function whitelistTab(): array
    {
        return [
            Section::make('Whitelist Settings')
                ->description('Control who may join without opening whitelist.json by hand.')
                ->columns(2)
                ->schema([
                    $this->booleanToggle('white_list', 'Enable Whitelist', 'Only players listed below may join.')->live(),
                    $this->booleanToggle('enforce_whitelist', 'Enforce Whitelist', 'Immediately removes players who are no longer whitelisted.'),
                ]),

            Section::make('Allowed Players')
                ->description('Add or remove Minecraft usernames. Existing UUIDs are preserved; new UUIDs are resolved automatically when you save.')
                ->schema([
                    TagsInput::make('whitelist_players')
                        ->label('Whitelisted Players')
                        ->placeholder('PlayerName')
                        ->helperText('Type a username and press Enter. When Online Mode is enabled, new usernames are resolved through Minecraft profile services. Offline-mode UUIDs are generated locally.')
                        ->columnSpanFull(),
                ]),
        ];
    }

    private function worldTab(): array
    {
        return [
            Section::make('World Selection')
                ->description('Changing the world name or generation settings can cause Minecraft to create a different world on the next start.')
                ->columns(2)
                ->schema([
                    TextInput::make('level_name')
                        ->label('World Name / Folder')
                        ->helperText('This is level-name. Use the Worlds page to delete an old world when swapping modpacks.')
                        ->required(),

                    TextInput::make('level_seed')
                        ->label('Seed')
                        ->helperText('Leave blank for a random seed.'),

                    Select::make('level_type')
                        ->label('World Type')
                        ->options($this->levelTypeOptions())
                        ->searchable()
                        ->selectablePlaceholder(false)
                        ->helperText('Custom modpack world types already present in server.properties are kept as an option.'),

                    Textarea::make('generator_settings')
                        ->label('Generator Settings')
                        ->rows(2)
                        ->helperText('Usually leave blank unless using a custom/flat world preset.')
                        ->columnSpanFull(),
                ]),

            Section::make('World Generation')
                ->columns(2)
                ->schema([
                    $this->booleanToggle('generate_structures', 'Generate Structures'),

                    TextInput::make('max_world_size')
                        ->label('Max World Size')
                        ->numeric()
                        ->minValue(1)
                        ->maxValue(29999984),

                    TextInput::make('initial_enabled_packs')
                        ->label('Initially Enabled Data Packs')
                        ->helperText('Comma-separated. Usually: vanilla'),

                    TextInput::make('initial_disabled_packs')
                        ->label('Initially Disabled Data Packs')
                        ->helperText('Comma-separated. Usually blank.'),
                ]),
        ];
    }

    private function networkTab(): array
    {
        return [
            Section::make('Address & Port')
                ->columns(2)
                ->schema([
                    TextInput::make('server_ip')
                        ->label('Server IP')
                        ->helperText('Normally leave blank in Pelican. Binding to the wrong IP can prevent the server from starting.'),

                    TextInput::make('server_port')
                        ->label('Server Port')
                        ->numeric()
                        ->minValue(1)
                        ->maxValue(65535)
                        ->helperText('Should normally match the server allocation in Pelican. Changing only this value can break connections.'),

                    $this->booleanToggle('enable_status', 'Server List Status', 'Allow the server to answer multiplayer status/ping requests.'),
                    $this->booleanToggle('hide_online_players', 'Hide Online Players', 'Hide the player sample from the multiplayer status response.'),
                ]),

            Section::make('Connection & Authentication')
                ->columns(2)
                ->schema([
                    $this->booleanToggle('prevent_proxy_connections', 'Prevent Proxy Connections'),
                    $this->booleanToggle('enforce_secure_profile', 'Enforce Secure Profile'),
                    $this->booleanToggle('use_native_transport', 'Use Native Transport', 'Use optimized Linux networking when available.'),
                    $this->booleanToggle('log_ips', 'Log Player IPs'),
                    $this->booleanToggle('accepts_transfers', 'Accept Player Transfers', 'Newer Minecraft versions only; ignored by older versions if absent/unsupported.'),

                    TextInput::make('network_compression_threshold')
                        ->label('Compression Threshold')
                        ->numeric()
                        ->minValue(-1)
                        ->helperText('-1 disables network compression.'),

                    TextInput::make('rate_limit')
                        ->label('Packet Rate Limit')
                        ->numeric()
                        ->minValue(0)
                        ->helperText('0 disables the rate limit.'),
                ]),
        ];
    }

    private function rconQueryTab(): array
    {
        return [
            Section::make('RCON')
                ->description('Remote console access. If you expose RCON outside the server container, use a strong password.')
                ->columns(2)
                ->schema([
                    $this->booleanToggle('enable_rcon', 'Enable RCON')->live(),

                    TextInput::make('rcon_port')
                        ->label('RCON Port')
                        ->numeric()
                        ->minValue(1)
                        ->maxValue(65535)
                        ->visible(fn (Get $get): bool => (bool) $get('enable_rcon')),

                    TextInput::make('rcon_password')
                        ->label('RCON Password')
                        ->password()
                        ->revealable()
                        ->maxLength(256)
                        ->visible(fn (Get $get): bool => (bool) $get('enable_rcon'))
                        ->columnSpanFull(),
                ]),

            Section::make('Query')
                ->columns(2)
                ->schema([
                    $this->booleanToggle('enable_query', 'Enable Query')->live(),

                    TextInput::make('query_port')
                        ->label('Query Port')
                        ->numeric()
                        ->minValue(1)
                        ->maxValue(65535)
                        ->visible(fn (Get $get): bool => (bool) $get('enable_query')),
                ]),

            Section::make('Monitoring')
                ->columns(2)
                ->schema([
                    $this->booleanToggle('enable_jmx_monitoring', 'Enable JMX Monitoring'),
                ]),
        ];
    }

    private function performanceTab(): array
    {
        return [
            Section::make('Distance & Entity Traffic')
                ->columns(2)
                ->schema([
                    TextInput::make('view_distance')
                        ->label('View Distance')
                        ->numeric()
                        ->minValue(2)
                        ->maxValue(64),

                    TextInput::make('simulation_distance')
                        ->label('Simulation Distance')
                        ->numeric()
                        ->minValue(2)
                        ->maxValue(64),

                    TextInput::make('entity_broadcast_range_percentage')
                        ->label('Entity Broadcast Range %')
                        ->numeric()
                        ->minValue(10)
                        ->maxValue(1000),
                ]),

            Section::make('Server Performance')
                ->columns(2)
                ->schema([
                    TextInput::make('max_tick_time')
                        ->label('Max Tick Time (ms)')
                        ->numeric()
                        ->minValue(-1)
                        ->helperText('-1 disables the watchdog timeout.'),

                    TextInput::make('max_chained_neighbor_updates')
                        ->label('Max Chained Neighbor Updates')
                        ->numeric()
                        ->minValue(-1),

                    $this->booleanToggle('sync_chunk_writes', 'Synchronous Chunk Writes'),

                    TextInput::make('pause_when_empty_seconds')
                        ->label('Pause When Empty (seconds)')
                        ->numeric()
                        ->minValue(-1)
                        ->helperText('Only used by newer versions that support this setting.'),
                ]),
        ];
    }

    private function resourcePackTab(): array
    {
        return [
            Section::make('Server Resource Pack')
                ->columns(2)
                ->schema([
                    TextInput::make('resource_pack')
                        ->label('Resource Pack URL')
                        ->url()
                        ->live()
                        ->columnSpanFull(),

                    TextInput::make('resource_pack_sha1')
                        ->label('SHA-1 Hash')
                        ->maxLength(40)
                        ->visible(fn (Get $get): bool => filled($get('resource_pack'))),

                    TextInput::make('resource_pack_id')
                        ->label('Resource Pack ID')
                        ->helperText('Optional UUID on newer versions.')
                        ->visible(fn (Get $get): bool => filled($get('resource_pack'))),

                    $this->booleanToggle('require_resource_pack', 'Require Resource Pack')
                        ->visible(fn (Get $get): bool => filled($get('resource_pack'))),

                    Textarea::make('resource_pack_prompt')
                        ->label('Resource Pack Prompt')
                        ->rows(2)
                        ->visible(fn (Get $get): bool => filled($get('resource_pack')))
                        ->columnSpanFull(),
                ]),

            Section::make('Links')
                ->columns(2)
                ->schema([
                    TextInput::make('bug_report_link')
                        ->label('Bug Report Link')
                        ->url()
                        ->helperText('Optional. Supported by newer Minecraft versions.'),
                ]),
        ];
    }

    private function advancedTab(): array
    {
        return [
            Section::make('Advanced Vanilla Settings')
                ->columns(2)
                ->schema([
                    TextInput::make('text_filtering_config')
                        ->label('Text Filtering Config')
                        ->helperText('Usually blank.'),

                    TextInput::make('region_file_compression')
                        ->label('Region File Compression')
                        ->helperText('Newer versions only. Leave unchanged unless you know the version supports it.'),

                    TextInput::make('status_heartbeat_interval')
                        ->label('Status Heartbeat Interval')
                        ->numeric()
                        ->minValue(0)
                        ->helperText('Used by the Minecraft Server Management Protocol on versions that support it.'),
                ]),

            Section::make('Server Management API')
                ->description('Minecraft 1.21.9+ only. Leave disabled unless you intentionally use the Minecraft Server Management Protocol.')
                ->columns(2)
                ->collapsed()
                ->collapsible()
                ->schema([
                    $this->booleanToggle('management_server_enabled', 'Enable Management API')->live(),

                    TextInput::make('management_server_host')
                        ->label('Management Host')
                        ->visible(fn (Get $get): bool => (bool) $get('management_server_enabled')),

                    TextInput::make('management_server_port')
                        ->label('Management Port')
                        ->numeric()
                        ->minValue(0)
                        ->maxValue(65535)
                        ->helperText('0 lets Minecraft choose an available port.')
                        ->visible(fn (Get $get): bool => (bool) $get('management_server_enabled')),

                    TextInput::make('management_server_secret')
                        ->label('Management Secret')
                        ->password()
                        ->revealable()
                        ->maxLength(40)
                        ->helperText('Leave blank to let supported Minecraft versions generate a secret.')
                        ->visible(fn (Get $get): bool => (bool) $get('management_server_enabled')),

                    TextInput::make('management_server_allowed_origins')
                        ->label('Allowed Browser Origins')
                        ->helperText('Minecraft 1.21.11+ browser authentication. Leave blank unless needed.')
                        ->visible(fn (Get $get): bool => (bool) $get('management_server_enabled'))
                        ->columnSpanFull(),

                    $this->booleanToggle('management_server_tls_enabled', 'Management TLS', 'TLS is enabled by default on supported Minecraft versions and requires a PKCS12 keystore.')->live()
                        ->visible(fn (Get $get): bool => (bool) $get('management_server_enabled')),

                    TextInput::make('management_server_tls_keystore')
                        ->label('TLS Keystore Path')
                        ->visible(fn (Get $get): bool => (bool) $get('management_server_enabled') && (bool) $get('management_server_tls_enabled')),

                    TextInput::make('management_server_tls_keystore_password')
                        ->label('TLS Keystore Password')
                        ->password()
                        ->revealable()
                        ->visible(fn (Get $get): bool => (bool) $get('management_server_enabled') && (bool) $get('management_server_tls_enabled')),
                ]),

            Section::make('Server Code of Conduct')
                ->description('Minecraft 1.21.9+ only. The default English text is stored in codeofconduct/en_us.txt.')
                ->collapsed()
                ->collapsible()
                ->schema([
                    $this->booleanToggle('enable_code_of_conduct', 'Enable Code of Conduct')->live(),

                    Textarea::make('code_of_conduct_text')
                        ->label('English Code of Conduct')
                        ->rows(10)
                        ->helperText('Shown to players when no language-specific file is available.')
                        ->visible(fn (Get $get): bool => (bool) $get('enable_code_of_conduct'))
                        ->columnSpanFull(),
                ]),

            Section::make('Other / Modpack-Specific Properties')
                ->description('Every server.properties key not covered by a friendly control appears here. You can edit, add, or remove entries, so modpack-specific and future Minecraft settings are never locked away.')
                ->collapsible()
                ->schema([
                    KeyValue::make('other_properties')
                        ->label('Other server.properties settings')
                        ->keyLabel('Property')
                        ->valueLabel('Value')
                        ->addActionLabel('Add property')
                        ->reorderable(false)
                        ->columnSpanFull(),
                ]),
        ];
    }

    private function booleanToggle(string $name, string $label, ?string $helperText = null): Toggle
    {
        $toggle = Toggle::make($name)
            ->label($label)
            ->inline(false)
            ->onIcon('tabler-check')
            ->offIcon('tabler-x')
            ->onColor('success')
            ->offColor('danger')
            ->stateCast(new BooleanStateCast(false));

        if ($helperText !== null) {
            $toggle->helperText($helperText);
        }

        return $toggle;
    }

    private function levelTypeOptions(): array
    {
        $options = [
            'minecraft:normal' => 'Normal',
            'default' => 'Normal (legacy name)',
            'minecraft:flat' => 'Superflat',
            'flat' => 'Superflat (legacy name)',
            'minecraft:large_biomes' => 'Large Biomes',
            'largebiomes' => 'Large Biomes (legacy name)',
            'minecraft:amplified' => 'Amplified',
            'amplified' => 'Amplified (legacy name)',
        ];

        $current = $this->detectedProperties['level-type'] ?? null;
        if (filled($current) && !array_key_exists($current, $options)) {
            $options[$current] = $current . ' (current / modpack custom)';
        }

        return $options;
    }

    private function definitions(): array
    {
        return [
            'motd' => ['property' => 'motd', 'type' => 'string', 'default' => 'A Minecraft Server'],
            'max_players' => ['property' => 'max-players', 'type' => 'int', 'default' => 20],
            'player_idle_timeout' => ['property' => 'player-idle-timeout', 'type' => 'int', 'default' => 0],
            'gamemode' => ['property' => 'gamemode', 'type' => 'string', 'default' => 'survival'],
            'difficulty' => ['property' => 'difficulty', 'type' => 'string', 'default' => 'easy'],
            'online_mode' => ['property' => 'online-mode', 'type' => 'bool', 'default' => true],
            'white_list' => ['property' => 'white-list', 'type' => 'bool', 'default' => false],
            'enforce_whitelist' => ['property' => 'enforce-whitelist', 'type' => 'bool', 'default' => false],
            'force_gamemode' => ['property' => 'force-gamemode', 'type' => 'bool', 'default' => false],
            'hardcore' => ['property' => 'hardcore', 'type' => 'bool', 'default' => false],
            'pvp' => ['property' => 'pvp', 'type' => 'bool', 'default' => true],

            'allow_flight' => ['property' => 'allow-flight', 'type' => 'bool', 'default' => false],
            'enable_command_block' => ['property' => 'enable-command-block', 'type' => 'bool', 'default' => false],
            'op_permission_level' => ['property' => 'op-permission-level', 'type' => 'int', 'default' => 4],
            'function_permission_level' => ['property' => 'function-permission-level', 'type' => 'int', 'default' => 2],
            'spawn_protection' => ['property' => 'spawn-protection', 'type' => 'int', 'default' => 16],
            'broadcast_console_to_ops' => ['property' => 'broadcast-console-to-ops', 'type' => 'bool', 'default' => true],
            'broadcast_rcon_to_ops' => ['property' => 'broadcast-rcon-to-ops', 'type' => 'bool', 'default' => true],
            'allow_nether' => ['property' => 'allow-nether', 'type' => 'bool', 'default' => true],
            'spawn_animals' => ['property' => 'spawn-animals', 'type' => 'bool', 'default' => true],
            'spawn_monsters' => ['property' => 'spawn-monsters', 'type' => 'bool', 'default' => true],
            'spawn_npcs' => ['property' => 'spawn-npcs', 'type' => 'bool', 'default' => true],

            'level_name' => ['property' => 'level-name', 'type' => 'string', 'default' => 'world'],
            'level_seed' => ['property' => 'level-seed', 'type' => 'string', 'default' => ''],
            'level_type' => ['property' => 'level-type', 'type' => 'string', 'default' => 'minecraft:normal'],
            'generator_settings' => ['property' => 'generator-settings', 'type' => 'string', 'default' => '{}'],
            'generate_structures' => ['property' => 'generate-structures', 'type' => 'bool', 'default' => true],
            'max_world_size' => ['property' => 'max-world-size', 'type' => 'int', 'default' => 29999984],
            'initial_enabled_packs' => ['property' => 'initial-enabled-packs', 'type' => 'string', 'default' => 'vanilla'],
            'initial_disabled_packs' => ['property' => 'initial-disabled-packs', 'type' => 'string', 'default' => ''],

            'server_ip' => ['property' => 'server-ip', 'type' => 'string', 'default' => ''],
            'server_port' => ['property' => 'server-port', 'type' => 'int', 'default' => 25565],
            'enable_status' => ['property' => 'enable-status', 'type' => 'bool', 'default' => true],
            'hide_online_players' => ['property' => 'hide-online-players', 'type' => 'bool', 'default' => false],
            'prevent_proxy_connections' => ['property' => 'prevent-proxy-connections', 'type' => 'bool', 'default' => false],
            'enforce_secure_profile' => ['property' => 'enforce-secure-profile', 'type' => 'bool', 'default' => true],
            'use_native_transport' => ['property' => 'use-native-transport', 'type' => 'bool', 'default' => true],
            'log_ips' => ['property' => 'log-ips', 'type' => 'bool', 'default' => true],
            'accepts_transfers' => ['property' => 'accepts-transfers', 'type' => 'bool', 'default' => false],
            'network_compression_threshold' => ['property' => 'network-compression-threshold', 'type' => 'int', 'default' => 256],
            'rate_limit' => ['property' => 'rate-limit', 'type' => 'int', 'default' => 0],

            'enable_rcon' => ['property' => 'enable-rcon', 'type' => 'bool', 'default' => false],
            'rcon_port' => ['property' => 'rcon.port', 'type' => 'int', 'default' => 25575],
            'rcon_password' => ['property' => 'rcon.password', 'type' => 'string', 'default' => ''],
            'enable_query' => ['property' => 'enable-query', 'type' => 'bool', 'default' => false],
            'query_port' => ['property' => 'query.port', 'type' => 'int', 'default' => 25565],
            'enable_jmx_monitoring' => ['property' => 'enable-jmx-monitoring', 'type' => 'bool', 'default' => false],

            'view_distance' => ['property' => 'view-distance', 'type' => 'int', 'default' => 10],
            'simulation_distance' => ['property' => 'simulation-distance', 'type' => 'int', 'default' => 10],
            'entity_broadcast_range_percentage' => ['property' => 'entity-broadcast-range-percentage', 'type' => 'int', 'default' => 100],
            'max_tick_time' => ['property' => 'max-tick-time', 'type' => 'int', 'default' => 60000],
            'max_chained_neighbor_updates' => ['property' => 'max-chained-neighbor-updates', 'type' => 'int', 'default' => 1000000],
            'sync_chunk_writes' => ['property' => 'sync-chunk-writes', 'type' => 'bool', 'default' => true],
            'pause_when_empty_seconds' => ['property' => 'pause-when-empty-seconds', 'type' => 'int', 'default' => -1],

            'resource_pack' => ['property' => 'resource-pack', 'type' => 'string', 'default' => ''],
            'resource_pack_sha1' => ['property' => 'resource-pack-sha1', 'type' => 'string', 'default' => ''],
            'resource_pack_id' => ['property' => 'resource-pack-id', 'type' => 'string', 'default' => ''],
            'require_resource_pack' => ['property' => 'require-resource-pack', 'type' => 'bool', 'default' => false],
            'resource_pack_prompt' => ['property' => 'resource-pack-prompt', 'type' => 'string', 'default' => ''],
            'bug_report_link' => ['property' => 'bug-report-link', 'type' => 'string', 'default' => ''],

            'text_filtering_config' => ['property' => 'text-filtering-config', 'type' => 'string', 'default' => ''],
            'region_file_compression' => ['property' => 'region-file-compression', 'type' => 'string', 'default' => 'deflate'],
            'status_heartbeat_interval' => ['property' => 'status-heartbeat-interval', 'type' => 'int', 'default' => 0],
            'management_server_enabled' => ['property' => 'management-server-enabled', 'type' => 'bool', 'default' => false],
            'management_server_host' => ['property' => 'management-server-host', 'type' => 'string', 'default' => 'localhost'],
            'management_server_port' => ['property' => 'management-server-port', 'type' => 'int', 'default' => 0],
            'management_server_secret' => ['property' => 'management-server-secret', 'type' => 'string', 'default' => ''],
            'management_server_allowed_origins' => ['property' => 'management-server-allowed-origins', 'type' => 'string', 'default' => ''],
            'management_server_tls_enabled' => ['property' => 'management-server-tls-enabled', 'type' => 'bool', 'default' => true],
            'management_server_tls_keystore' => ['property' => 'management-server-tls-keystore', 'type' => 'string', 'default' => ''],
            'management_server_tls_keystore_password' => ['property' => 'management-server-tls-keystore-password', 'type' => 'string', 'default' => ''],
            'enable_code_of_conduct' => ['property' => 'enable-code-of-conduct', 'type' => 'bool', 'default' => false],
        ];
    }

    private function makeFormState(array $properties): array
    {
        $state = [];

        foreach ($this->definitions() as $formKey => $definition) {
            $property = $definition['property'];
            $raw = array_key_exists($property, $properties)
                ? $properties[$property]
                : $definition['default'];

            $state[$formKey] = $this->castValue($raw, $definition['type']);
        }

        return $state;
    }

    private function castValue(mixed $value, string $type): mixed
    {
        return match ($type) {
            'bool' => filter_var($value, FILTER_VALIDATE_BOOLEAN),
            'int' => is_numeric($value) ? (int) $value : 0,
            default => (string) $value,
        };
    }

    private function serializeValue(mixed $value, string $type): string
    {
        return match ($type) {
            'bool' => $value ? 'true' : 'false',
            'int' => (string) ((int) $value),
            default => str_replace(["\r", "\n"], ['', '\\n'], (string) $value),
        };
    }

    private function readPropertiesFile(Server $server): string
    {
        $repository = (new DaemonFileRepository())->setServer($server);

        return (string) $repository->getContent('server.properties');
    }

    private function parseProperties(string $raw): array
    {
        $properties = [];

        foreach (preg_split('/\R/', $raw) ?: [] as $line) {
            $trimmed = trim($line);

            if ($trimmed === '' || str_starts_with($trimmed, '#') || str_starts_with($trimmed, '!')) {
                continue;
            }

            $separator = strpos($line, '=');
            if ($separator === false) {
                $separator = strpos($line, ':');
            }

            if ($separator === false) {
                continue;
            }

            $key = trim(substr($line, 0, $separator));
            $value = trim(substr($line, $separator + 1));

            if ($key !== '') {
                $properties[$key] = $value;
            }
        }

        return $properties;
    }

    private function applyUpdates(string $raw, array $updates, array $removeKeys = []): string
    {
        $lines = preg_split('/\R/', $raw) ?: [];
        $seen = [];
        $remove = array_fill_keys($removeKeys, true);

        foreach ($lines as $index => $line) {
            $trimmed = trim($line);

            if ($trimmed === '' || str_starts_with($trimmed, '#') || str_starts_with($trimmed, '!')) {
                continue;
            }

            $separator = strpos($line, '=');
            if ($separator === false) {
                $separator = strpos($line, ':');
            }

            if ($separator === false) {
                continue;
            }

            $key = trim(substr($line, 0, $separator));

            if (isset($remove[$key])) {
                $lines[$index] = null;
                continue;
            }

            if (array_key_exists($key, $updates)) {
                $lines[$index] = $key . '=' . $updates[$key];
                $seen[$key] = true;
            }
        }

        $lines = array_values(array_filter($lines, fn ($line): bool => $line !== null));
        $missing = array_diff_key($updates, $seen);

        if (!empty($missing)) {
            if (!empty($lines) && end($lines) !== '') {
                $lines[] = '';
            }

            $lines[] = '# Added by Pelican Minecraft Server Config';

            foreach ($missing as $key => $value) {
                $lines[] = $key . '=' . $value;
            }
        }

        return rtrim(implode("\n", $lines)) . "\n";
    }

    private function unknownProperties(): array
    {
        return $this->unknownPropertiesFrom($this->detectedProperties);
    }

    private function unknownPropertiesFrom(array $properties): array
    {
        $known = [];

        foreach ($this->definitions() as $definition) {
            $known[$definition['property']] = true;
        }

        return array_diff_key($properties, $known);
    }

    private function sanitizeOtherProperties(mixed $properties): array
    {
        if (!is_array($properties)) {
            return [];
        }

        $known = [];
        foreach ($this->definitions() as $definition) {
            $known[$definition['property']] = true;
        }

        $clean = [];
        foreach ($properties as $key => $value) {
            $key = trim((string) $key);

            if ($key === ''
                || isset($known[$key])
                || str_contains($key, "\n")
                || str_contains($key, "\r")
                || str_contains($key, '=')
                || str_contains($key, ':')) {
                continue;
            }

            $clean[$key] = str_replace(["\r", "\n"], ['', '\\n'], (string) $value);
        }

        return $clean;
    }

    private function readWhitelistEntries(Server $server): array
    {
        try {
            $repository = (new DaemonFileRepository())->setServer($server);
            $raw = (string) $repository->getContent('whitelist.json');
            $decoded = json_decode($raw, true, 512, JSON_THROW_ON_ERROR);
        } catch (\Illuminate\Contracts\Filesystem\FileNotFoundException) {
            return [];
        }

        if (!is_array($decoded)) {
            return [];
        }

        $entries = [];
        foreach ($decoded as $entry) {
            if (!is_array($entry) || empty($entry['name']) || empty($entry['uuid'])) {
                continue;
            }

            $entries[] = [
                'uuid' => (string) $entry['uuid'],
                'name' => (string) $entry['name'],
            ];
        }

        return $entries;
    }

    private function buildWhitelistEntries(Server $server, mixed $names, bool $onlineMode, bool $forceResolve = false): array
    {
        $names = is_array($names) ? $names : [];
        $normalized = [];

        foreach ($names as $name) {
            $name = trim((string) $name);
            if ($name === '') {
                continue;
            }

            if (!preg_match('/^[A-Za-z0-9_]{1,16}$/', $name)) {
                throw new RuntimeException("Invalid Minecraft username: {$name}");
            }

            $normalized[strtolower($name)] = $name;
        }

        $existing = [];
        if (!$forceResolve) {
            foreach ($this->readWhitelistEntries($server) as $entry) {
                $existing[strtolower($entry['name'])] = $entry;
            }
        }

        $entries = [];
        foreach ($normalized as $lower => $name) {
            if (isset($existing[$lower])) {
                $entries[] = $existing[$lower];
                continue;
            }

            $entries[] = $onlineMode
                ? $this->lookupOnlineProfile($server, $name)
                : ['uuid' => $this->offlineUuid($name), 'name' => $name];
        }

        usort($entries, fn (array $a, array $b): int => strcasecmp($a['name'], $b['name']));

        return $entries;
    }

    private function writeWhitelistEntries(Server $server, array $entries): void
    {
        $json = json_encode($entries, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
        $repository = (new DaemonFileRepository())->setServer($server);
        $repository->putContent('whitelist.json', $json . "\n")->throw();
    }

    private function lookupOnlineProfile(Server $server, string $name): array
    {
        foreach ($this->readUserCacheEntries($server) as $entry) {
            if (strcasecmp($entry['name'], $name) === 0) {
                return $entry;
            }
        }

        $urls = [
            'https://api.minecraftservices.com/minecraft/profile/lookup/name/' . rawurlencode($name),
            'https://api.mojang.com/users/profiles/minecraft/' . rawurlencode($name),
        ];

        foreach ($urls as $url) {
            try {
                $response = Http::timeout(10)->acceptJson()->get($url);
                if (!$response->successful()) {
                    continue;
                }

                $id = (string) ($response->json('id') ?? '');
                $resolvedName = (string) ($response->json('name') ?? $name);
                $uuid = $this->formatUuid($id);

                if ($uuid !== null) {
                    return ['uuid' => $uuid, 'name' => $resolvedName];
                }
            } catch (Exception) {
                continue;
            }
        }

        throw new RuntimeException("Could not resolve Minecraft profile for {$name}. Check the spelling or try again later.");
    }

    private function readUserCacheEntries(Server $server): array
    {
        try {
            $repository = (new DaemonFileRepository())->setServer($server);
            $raw = (string) $repository->getContent('usercache.json');
            $decoded = json_decode($raw, true, 512, JSON_THROW_ON_ERROR);
        } catch (Exception) {
            return [];
        }

        if (!is_array($decoded)) {
            return [];
        }

        $entries = [];
        foreach ($decoded as $entry) {
            if (!is_array($entry) || empty($entry['name']) || empty($entry['uuid'])) {
                continue;
            }

            $entries[] = [
                'uuid' => (string) $entry['uuid'],
                'name' => (string) $entry['name'],
            ];
        }

        return $entries;
    }

    private function offlineUuid(string $name): string
    {
        $bytes = unpack('C*', md5('OfflinePlayer:' . $name, true));
        if (!is_array($bytes)) {
            throw new RuntimeException("Could not generate an offline UUID for {$name}.");
        }

        $bytes[7] = ($bytes[7] & 0x0f) | 0x30;
        $bytes[9] = ($bytes[9] & 0x3f) | 0x80;

        $hex = '';
        foreach ($bytes as $byte) {
            $hex .= sprintf('%02x', $byte);
        }

        return $this->formatUuid($hex) ?? $hex;
    }

    private function formatUuid(string $uuid): ?string
    {
        $hex = strtolower(str_replace('-', '', trim($uuid)));
        if (!preg_match('/^[0-9a-f]{32}$/', $hex)) {
            return null;
        }

        return substr($hex, 0, 8) . '-'
            . substr($hex, 8, 4) . '-'
            . substr($hex, 12, 4) . '-'
            . substr($hex, 16, 4) . '-'
            . substr($hex, 20, 12);
    }

    private function validateSupplementalSettings(array $formData): void
    {
        if ((bool) ($formData['enable_code_of_conduct'] ?? false)
            && trim((string) ($formData['code_of_conduct_text'] ?? '')) === '') {
            throw new RuntimeException('Add English Code of Conduct text before enabling the Code of Conduct.');
        }

        if (!(bool) ($formData['management_server_enabled'] ?? false)) {
            return;
        }

        $secret = trim((string) ($formData['management_server_secret'] ?? ''));
        if ($secret !== '' && !preg_match('/^[A-Za-z0-9]{40}$/', $secret)) {
            throw new RuntimeException('The Management API secret must be exactly 40 letters or numbers, or left blank for Minecraft to generate one.');
        }

        if ((bool) ($formData['management_server_tls_enabled'] ?? true)
            && trim((string) ($formData['management_server_tls_keystore'] ?? '')) === '') {
            throw new RuntimeException('Management API TLS is enabled, but no PKCS12 keystore path is set. Add a keystore path or turn Management TLS off.');
        }
    }

    private function readOptionalTextFile(Server $server, string $path): string
    {
        try {
            $repository = (new DaemonFileRepository())->setServer($server);
            return (string) $repository->getContent($path);
        } catch (\Illuminate\Contracts\Filesystem\FileNotFoundException) {
            return '';
        }
    }

    private function writeCodeOfConduct(Server $server, array $formData): void
    {
        $enabled = (bool) ($formData['enable_code_of_conduct'] ?? false);
        $text = str_replace("\r\n", "\n", (string) ($formData['code_of_conduct_text'] ?? ''));

        if (!$enabled && trim($text) === '') {
            return;
        }

        $repository = (new DaemonFileRepository())->setServer($server);
        try {
            $repository->createDirectory('codeofconduct', '/');
        } catch (Exception) {
            
        }
        $repository->putContent('codeofconduct/en_us.txt', rtrim($text) . "\n")->throw();
    }

    private function applyWhitelistLive(Server $server, bool $enabled): bool
    {
        try {
            if (!$server->retrieveStatus()->isStartingOrRunning()) {
                return false;
            }

            $server->send($enabled ? 'whitelist on' : 'whitelist off');
            if ($enabled) {
                $server->send('whitelist reload');
            }

            return true;
        } catch (Exception) {
            return false;
        }
    }
}
