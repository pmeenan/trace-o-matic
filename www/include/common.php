<?php
$TITLE = "Trace-O-Matic";
$ERROR = null;
$ID = null;
$TEST_PATH = null;
$RUN = 0;
if (isset($_REQUEST['test'])) {
  if (preg_match('/^\w+$/', $_REQUEST['test'])) {
    $ID = $_REQUEST['test'];
    $TEST_PATH = '/results/' . str_replace('_', '/', $ID) . '/';
    if (!is_dir(__DIR__ . '/..' . $TEST_PATH)) {
      $ERROR = "Test not found";
    }
  } else {
    $ERROR = "Invalid test ID";
  }
}
if (isset($_REQUEST['run'])) {
  if (preg_match('/^\d+$/', $_REQUEST['run'])) {
    $RUN = intval($_REQUEST['run']);
  } else {
    $ERROR = "Invalid Run Number";
  }
}
