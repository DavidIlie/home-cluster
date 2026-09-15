<?php
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
return new class extends Migration {
    public function up(): void {
        Schema::create('davidapps_forward_addresses', function (Blueprint $table) {
            $table->id();
            $table->unsignedInteger('server_id')->unique();
            $table->uuid('server_uuid')->unique();
            $table->string('hostname')->unique();
            $table->string('backend');
            $table->string('challenge', 64);
            $table->text('error')->nullable();
            $table->timestamp('synced_at')->nullable();
        });
    }
    public function down(): void { Schema::dropIfExists('davidapps_forward_addresses'); }
};
