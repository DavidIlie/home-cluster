<?php
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
return new class extends Migration {
    public function up(): void {
        Schema::create('davidapps_theme_preferences', function (Blueprint $table) {
            $table->unsignedInteger('user_id')->primary();
            $table->string('theme', 40);
            $table->foreign('user_id')->references('id')->on('users')->cascadeOnDelete();
        });
    }
    public function down(): void { Schema::dropIfExists('davidapps_theme_preferences'); }
};
