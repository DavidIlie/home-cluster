<?php
require '/var/www/html/vendor/autoload.php';
$app=require '/var/www/html/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
use N3rdMade\MinecraftConfig\Filament\Server\Pages\MinecraftConfigPage as Page;
use Filament\Facades\Filament;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Http;
function check($value,$label){if(!$value)throw new RuntimeException($label);echo "PASS: $label\n";}
foreach([1,2] as $id){
 $server=App\Models\Server::find($id);Auth::loginUsingId($id);Filament::setTenant($server);
 check(Page::canAccess(),"owner $id can access config");
 $page=new Page();
 $method=new ReflectionMethod(Page::class,'readPropertiesFile');
 $raw=$method->invoke($page,$server);
 check(strlen($raw)>0,"server $id properties read through Wings");
}
Filament::setTenant(App\Models\Server::find(1));Auth::loginUsingId(2);
check(!Page::canAccess(),'foreign owner denied');
try{(new Page())->save();throw new RuntimeException('save allowed');}catch(Symfony\Component\HttpKernel\Exception\HttpException $e){check($e->getStatusCode()===403,'foreign save denied');}
Http::fake(['*'=>Http::response('Unavailable',503,['User-Agent'=>'Pelican Wings/v1.0.0 (id:'.App\Models\Server::find(1)->node->daemon_token_id.')'])]);
foreach(['readWhitelistEntries'=>[App\Models\Server::find(1)],'readOptionalTextFile'=>[App\Models\Server::find(1),'codeofconduct/en_us.txt']] as $method=>$args){
 try{(new ReflectionMethod(Page::class,$method))->invoke(new Page(),...$args);throw new RuntimeException('failure swallowed');}
 catch(Illuminate\Http\Client\RequestException $e){check($e->response->status()===503,"$method propagates outage instead of empty data");}
}
