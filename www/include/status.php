<?php
function get_test_status() {
  global $TEST_DIR;
  $status = array("heading" => "", "status" => "", "done" => false);
  $info = json_decode(file_get_contents("$TEST_DIR/testinfo.json"), true);
  if (!$info) {
    $status['heading'] = "Invalid test";
    $status['status'] = "Test not found";
  } elseif (is_file("$TEST_DIR/.done")) {
    $status['done'] = true;
    $status['heading'] = "Test is complete";
    $status['status'] = file_get_contents("$TEST_DIR/.done");
  } elseif (is_file("$TEST_DIR/.running")) {
    $status['heading'] = "Test is running";
    $status['status'] = file_get_contents("$TEST_DIR/.running");
  } elseif (is_file("$TEST_DIR/.building")) {
    $status['heading'] = "Test is building";
    $status['status'] = file_get_contents("$TEST_DIR/.building");
  } elseif (is_file("$TEST_DIR/.status")) {
    $status['heading'] = "Test is pending";
    $status['status'] = file_get_contents("$TEST_DIR/.status");
  } else {
    $status['heading'] = "Test is pending";
    if ($info['needs_build']) {
      $status['status'] = "Waiting for build bot";
    } else {
      $status['status'] = "Waiting to be tested";
    }
  }
  return $status;
}