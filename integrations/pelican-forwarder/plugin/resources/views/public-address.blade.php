<x-filament-panels::page>
    <x-filament::section heading="Join your server">
        <p class="text-2xl font-semibold"><code>{{ $address->hostname }}</code></p>
        <p class="mt-2 text-sm">Use this address in Minecraft Java. No port is needed.</p>
        <p class="mt-2 text-sm">{{ $address->error ?: ($address->synced_at ? 'Forwarding route provisioned.' : 'Provisioning the route; this takes up to one minute.') }}</p>
        <p class="mt-2 text-sm">{{ $dnsReady ? 'DNS points to the relay.' : 'DNS needs setup. Add the record below at your domain provider.' }}</p>
        <p class="mt-2 text-sm">A provisioned address does not mean the game is running. Start the server from Console when you want to play.</p>
    </x-filament::section>
    <x-filament::section heading="DNS setup">
        <p>Type: <code>CNAME</code></p>
        <p>Name: <code>{{ $address->hostname }}</code></p>
        <p>Target: <code>{{ $target }}</code></p>
        <p class="mt-2 text-sm">Use DNS only, with proxying disabled. At a zone apex, use an A record pointing to 79.76.102.151. Remove conflicting A or AAAA records. DNS changes may take time to appear.</p>
        <p class="mt-2 text-sm">Traffic travels through the public relay and WireGuard to this server’s allocated port.</p>
    </x-filament::section>
    @if ($this->canEdit())
    <x-filament::section heading="Use your own domain">
        <form wire:submit="save" class="space-y-4">
            <label for="public-hostname">Domain name</label>
            <x-filament::input.wrapper><x-filament::input id="public-hostname" wire:model="hostname" placeholder="play.example.com" /></x-filament::input.wrapper>
            @error('hostname') <p role="alert">{{ $message }}</p> @enderror
            <p class="text-sm">First add a TXT record named <code>_pelican.your-new-domain</code> with this value:</p>
            <p><code>{{ $address->challenge }}</code></p>
            <p class="text-sm">Also point your new domain’s CNAME to <code>{{ $target }}</code>. Saving switches the route from the old address to the new one.</p>
            <x-filament::button type="submit" wire:loading.attr="disabled">Verify ownership and save</x-filament::button>
        </form>
    </x-filament::section>
    @endif
</x-filament-panels::page>
