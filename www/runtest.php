<?php
include(__DIR__ . "/include/common.php");

function generate_test_id() {
  global $SETTINGS;
  $id = null;
  $results = $SETTINGS['results_dir'];
  do {
    $id = date("Ymd") . '_' . bin2hex(random_bytes(10));
  } while (is_dir("$results/$id"));
  return $id;
}

function get_test_settings() {
  global $SETTINGS;
  $test = array();

  if (isset($_REQUEST['url']) && filter_var($_REQUEST['url'], FILTER_VALIDATE_URL))
    $test['url'] = $_REQUEST['url'];
  if (isset($_REQUEST['runs']) && filter_var($_REQUEST['runs'], FILTER_VALIDATE_INT))
    $test['runs'] = intval($_REQUEST['runs']);
  if (isset($_REQUEST['cl']) && filter_var($_REQUEST['cl'], FILTER_VALIDATE_INT))
    $test['cl'] = intval($_REQUEST['cl']);
  $test['rebuild'] = isset($_REQUEST['rebuild']) && $_REQUEST['rebuild'];
  $test['clear'] = isset($_REQUEST['clear']) && $_REQUEST['clear'];
  $test['video'] = isset($_REQUEST['video']) && $_REQUEST['video'];
  $test['cpu'] = isset($_REQUEST['cpu']) && $_REQUEST['cpu'];
  $categories = array();
  if (isset($_REQUEST['categories']) && is_array($_REQUEST['categories'])) {
    foreach($_REQUEST['categories'] as $category) {
      if (in_array($category, $SETTINGS['trace_categories'])) {
        $categories[] = $category;
      }
    }
  }
  if (count($categories))
    $test['categories'] = $categories;

  if (isset($test['url']) && isset($test['runs'])) {
    $test['id'] = generate_test_id();
    return $test;
  } else {
    return null;
  }
}

$test = get_test_settings();
if (isset($test)) {
  $path = str_replace('_', '/', $test['id']);
  $dir = "{$SETTINGS['results_dir']}/$path";
  mkdir($dir, 0777, true);
  file_put_contents("$dir/testinfo.json", json_encode($test));

  // TODO submit the test the appropriate beanstalk queue (build or test)

  header("Location: {$SETTINGS['root_url']}view.php?test={$test['id']}");
  exit(0);
} else {
  $ERROR = "Error with test request";
  include(__DIR__ . "/error.php");
  exit(0);
}