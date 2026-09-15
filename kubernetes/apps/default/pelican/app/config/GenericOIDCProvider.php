<?php

namespace Boy132\GenericOIDCProviders\Extensions\OAuth\Providers;

use Override;
use SocialiteProviders\OIDC\Provider;
use UnexpectedValueException;

final class GenericOIDCProvider extends Provider
{
    public static function additionalConfigKeys(): array
    {
        return array_merge(parent::additionalConfigKeys(), ['use_pkce']);
    }

    #[Override]
    protected function usesPKCE(): bool
    {
        return $this->config['use_pkce'] ?? true;
    }

    #[Override]
    protected function shouldVerifyJwt(): bool
    {
        return true;
    }

    #[Override]
    protected function verifyAndDecodeJWT($jwt)
    {
        $claims = parent::verifyAndDecodeJWT($jwt);
        $clientId = $this->getConfig('client_id');
        $audiences = (array) ($claims->aud ?? []);

        if (($claims->iss ?? null) !== 'https://id.davidapps.dev'
            || !in_array($clientId, $audiences, true)
            || (isset($claims->azp) && $claims->azp !== $clientId)
            || (count($audiences) > 1 && ($claims->azp ?? null) !== $clientId)
            || ($claims->email_verified ?? null) !== true
            || !is_string($claims->sub ?? null)
            || $claims->sub === '') {
            throw new UnexpectedValueException('Invalid DavidApps identity claims.');
        }

        $this->request->session()->forget('nonce');

        return $claims;
    }
}
