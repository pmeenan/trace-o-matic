<?php
include(__DIR__ . "/include/common.php");
if (isset($ID)) {
  $TITLE = "$ID Results : Trace-O-Matic";
  $info = json_decode(file_get_contents("$TEST_DIR/testinfo.json"), true);
  if (!$info || !isset($info['url']) || !isset($info['runs'])) {
    $ERROR = "Invalid test";
  }
} else {
  $ERROR = "Missing test ID";
}
include(__DIR__ . "/include/header.php");
require_once(__DIR__ . "/include/status.php");

if (is_file("$TEST_DIR/.done")) {
  echo "<h1>Test-O-Matic Test Results</h1>\n";
  $url = htmlspecialchars($info['url']);
  echo "<p>URL Tested: <a href='$url'>$url</a><br>\n";
  echo "Runs: {$info['runs']}</p>\n";

  for ($run = 1; $run <= $info['runs']; $run++) {
    echo "<h2>Run # $run</h2>\n";
    echo "<div class='result'>";
    $n = sprintf("%03d", $run);
    if (is_file("$TEST_DIR/$n-screenshot.png")) {
      echo "<div class='thumbnail'><a href='{$TEST_PATH}$n-screenshot.png'><img src='{$TEST_PATH}$n-screenshot.png'></a></div>";
    }
    echo "<div class='links'>";
    echo "<h3>Trace</h3>";
    echo "View in:<ul>\n";
    if (is_file("$TEST_DIR/$n-trace.perfetto.gz")) {
      echo "<li><a href='trace.php?test=$ID&run=$run' target='_blank' rel='noopener'>Perfetto</a></li>";
    }
    if (is_file("$TEST_DIR/$n-trace.json.gz")) {
      echo "<li><a href='devtools.php?test=$ID&run=$run' target='_blank' rel='noopener'>Dev Tools</a></li>";
    }
    echo "</ul>Download Trace:<ul>\n";
    if (is_file("$TEST_DIR/$n-trace.perfetto.gz")) {
      echo "<li><a href='{$TEST_PATH}$n-trace.perfetto.gz'>Protobuf Format</a></li>";
    }
    if (is_file("$TEST_DIR/$n-trace.json.gz")) {
      echo "<li><a href='{$TEST_PATH}$n-trace.json.gz'>JSON</a></li>";
    }
    echo "</ul></div>";
    echo "</div>"; // result
  }
} else {
  $status = get_test_status();
  echo("<h2 id='heading'>{$status['heading']}</h2>\n<p id='status'>" . htmlspecialchars($status['status']) . "</p>");
}
?>

<?php
include(__DIR__ . "/include/footer.php");