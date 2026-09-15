#!/bin/sh
set -eu
cd /var/www/html
composer require --no-scripts --no-interaction --update-no-dev --minimal-changes \
  'kovah/laravel-socialite-oidc:0.8.0' \
  'xpaw/php-minecraft-query:5.0.0' \
  'xpaw/php-source-query-class:6.0.0'
yarn install --frozen-lockfile
yarn build
exec /bin/ash /entrypoint.sh supervisord -n -c /etc/supervisord.conf
