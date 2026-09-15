<?php
require '/var/www/html/vendor/autoload.php';
$app=require '/var/www/html/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
use Illuminate\Support\Facades\DB;
use App\Models\Server;
use DavidApps\Forwarder\Services\Forwarder;
function check($ok,$name){if(!$ok)throw new RuntimeException($name);echo "PASS: $name\n";}
$f=app(Forwarder::class);
$f->syncAll();
$before=$f->request('GET')['mappings'];
check(count($before)===2,'two original routes present');
check($f->dns('im.gurt.ing') && $f->dns('mc.anaxax.tv'),'existing DNS verified');
check(!$f->supports(Server::find(4)),'Hytale excluded from Minecraft relay');
$uuid=(string)Illuminate\Support\Str::uuid();
$host=substr($uuid,0,8).'.mc-forward.davidapps.dev';
DB::beginTransaction();
try {
 $attrs=Server::find(1)->getRawOriginal();unset($attrs['id']);
 $attrs['uuid']=$uuid;if(array_key_exists('uuid_short',$attrs))$attrs['uuid_short']=substr($uuid,0,8);
 $attrs['name']='Provisioning transaction test';
 $id=DB::table('servers')->insertGetId($attrs);
 $server=Server::find($id);
 $f->syncAll();
 $row=$f->address($server);$host=$row->hostname;
 check(($f->request('GET')['active'][$host]??null)==='192.168.100.163:25565','new Minecraft server gets active route');
 check($f->dns($host),'new default hostname resolves without manual DNS');
 DB::table('servers')->where('id',$id)->update(['allocation_id'=>Server::find(2)->allocation_id]);
 $f->syncAll();
 check(($f->request('GET')['active'][$host]??null)==='192.168.100.163:25566','primary allocation change updates route');
 try {$f->change(Server::find($id),'unowned.example.com');throw new RuntimeException('unowned domain accepted');}catch(Illuminate\Validation\ValidationException $e){check(true,'custom domain without TXT proof rejected');}
 Illuminate\Support\Facades\Auth::loginUsingId(2);
 Filament\Facades\Filament::setTenant(Server::find(1));
 $page=new DavidApps\Forwarder\Filament\Pages\PublicAddress();
 check(!$page->canEdit(),'Enrico cannot edit David’s address');
 try {$page->save();throw new RuntimeException('foreign edit accepted');}catch(Symfony\Component\HttpKernel\Exception\HttpException $e){check($e->getStatusCode()===403,'foreign server mutation blocked');}
 Filament\Facades\Filament::setTenant(Server::find(2));
 check($page->canEdit(),'Enrico can manage his own address');
 DB::table('servers')->where('id',$id)->delete();
 $f->syncAll();
 retry(10,function()use($f,$host){if(isset($f->request('GET')['active'][$host]))throw new RuntimeException('still active');},200);
 check(!DB::table('davidapps_forward_addresses')->where('server_id',$id)->exists(),'deleted server route cleaned up');
} finally {
 DB::rollBack();
 $f->request('DELETE',['hostname'=>$host,'owner'=>$uuid,'backend'=>'192.168.100.163:25565']);
}
check($f->request('GET')['mappings']===$before,'original routes intact after lifecycle test');
check(Server::count()===3,'no test servers retained');
