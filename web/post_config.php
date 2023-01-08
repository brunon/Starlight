<?php
$responseBody = file_get_contents('php://input');
$json = json_decode($responseBody);
header('Content-Type: application/json');
if($json){
    $path = getcwd() . '/config.json';
    $fp = fopen($path, 'w');
    fwrite($fp, json_encode($json, JSON_PRETTY_PRINT));
    fclose($fp);
    $response = '{"success":true}';
}
else{
    $response = '{"success":false}';
}
echo $response;
?>
