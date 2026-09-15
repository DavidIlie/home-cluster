<?php
$path = '/var/www/html/plugins/concierge/src/Llm/Providers/OpenAiCompatibleProvider.php';
$source = file_get_contents($path);
$marker = "        if (\$tools !== []) {";
$addition = "        if (\$this->settings->model === 'gpt-5.6-luna') {\n            \$payload['reasoning_effort'] = 'low';\n        }\n\n";
if (!str_contains($source, "\$payload['reasoning_effort']")) {
    if (substr_count($source, $marker) !== 1) {
        throw new RuntimeException('Concierge adapter changed; review the reasoning patch.');
    }
    file_put_contents($path, str_replace($marker, $addition . $marker, $source));
}
