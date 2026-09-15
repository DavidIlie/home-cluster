<?php
require '/var/www/html/vendor/autoload.php';
$app=require '/var/www/html/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
$f=app(DavidApps\Forwarder\Services\Forwarder::class);
$before=$f->request('GET');
$body=['hostname'=>'provision-test.mc-forward.davidapps.dev','owner'=>'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee','backend'=>'192.168.100.163:25599'];
function check($condition,$name){if(!$condition)throw new RuntimeException($name);echo "PASS: $name\n";}
check(Illuminate\Support\Facades\Http::get('http://192.168.2.5:8091/routes')->status()===401,'unauthenticated request rejected');
try {
 try {$f->request('PUT',[...$body,'backend'=>'127.0.0.1:22']);throw new RuntimeException('accepted');}catch(Illuminate\Http\Client\RequestException $e){check($e->response->status()===422,'arbitrary backend rejected');}
 $f->request('PUT',$body);
 retry(10,function()use($f,$body){if(($f->request('GET')['active'][$body['hostname']]??null)!==$body['backend'])throw new RuntimeException('not active');},200);
 check($f->request('GET')['mappings'][$body['hostname']]===$body['backend'],'new route persisted and active');
 try {$f->request('PUT',[...$body,'owner'=>'bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee']);throw new RuntimeException('accepted');}catch(Illuminate\Http\Client\RequestException $e){check($e->response->status()===409,'another server cannot take hostname');}
 try {$f->request('DELETE',[...$body,'owner'=>'bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee']);throw new RuntimeException('accepted');}catch(Illuminate\Http\Client\RequestException $e){check($e->response->status()===409,'another server cannot delete hostname');}
} finally {$f->request('DELETE',$body);}
retry(10,function()use($f,$before){if($f->request('GET')['active']!==$before['active'])throw new RuntimeException('routes differ');},200);
check($f->request('GET')['mappings']===$before['mappings'],'test route removed and original routes preserved');
