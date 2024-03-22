<?php
include(__DIR__ . "/include/common.php");
require_once(__DIR__ . "/include/status.php");
$status = array("done" => false);
if (isset($ERROR)) {
  $status['heading'] = "Error";
  $status['status'] = $ERROR;
} elseif (isset($ID)) {
  $stat = get_test_status();
  $status['heading'] = $stat['heading'];
  $status['status'] = $stat['status'];
  $status['done'] = $stat['done'];
} else {
  $status['heading'] = "Error";
  $status['status'] = "Invalid test";
}
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
echo(json_encode($status));