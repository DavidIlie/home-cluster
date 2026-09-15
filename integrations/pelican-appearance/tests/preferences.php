<?php
require '/var/www/html/vendor/autoload.php';
$app=require '/var/www/html/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
use DavidApps\Appearance\ThemePreference;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\DB;
function check($ok,$label){if(!$ok)throw new RuntimeException($label);echo "PASS: $label\n";}
Auth::loginUsingId(1);check(ThemePreference::current()==='mocha','David has Mocha');
Auth::loginUsingId(2);check(ThemePreference::current()==='hairline','Enrico retains Hairline');
DB::beginTransaction();
try {
 Auth::loginUsingId(1);ThemePreference::save('nord');
 Auth::loginUsingId(2);check(ThemePreference::current()==='hairline','David theme change leaves Enrico unchanged');
 ThemePreference::save('default');
 Auth::loginUsingId(1);check(ThemePreference::current()==='nord','Enrico theme change leaves David unchanged');
 try{ThemePreference::save('../../bad');throw new RuntimeException('invalid theme accepted');}catch(Illuminate\Validation\ValidationException){check(true,'unknown theme rejected');}
 Auth::logout();try{ThemePreference::save('nord');throw new RuntimeException('guest saved');}catch(Symfony\Component\HttpKernel\Exception\HttpException $e){check($e->getStatusCode()===403,'guest cannot save a preference');}
} finally {DB::rollBack();}
$manifest=json_decode(file_get_contents('/var/www/html/public/build/manifest.json'),true);
foreach(['nord-theme','catppuccin-mocha-theme'] as $id)check(isset($manifest["plugins/$id/resources/css/theme.css"]),"$id assets built");
