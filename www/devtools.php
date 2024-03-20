<?php
include(__DIR__ . "/include/common.php");
if (isset($ID) && isset($RUN)) {
  $TITLE = "$ID.$RUN Dev Tools : Trace-O-Matic";
  $traceUrl = $TEST_PATH . sprintf("%03d-trace.json.gz", $RUN);
  if (is_file(__DIR__ . $traceUrl)) {
    $traceUrl = "{$SETTINGS['root_url']}$traceUrl";
  } else {
    $ERROR = "Trace not found";
  }
} else {
  $ERROR = "Invalid trace";
}
$CSS = "body {margin:0px;padding:0px;overflow:hidden}\n";
include(__DIR__ . "/include/header.php");
?>
  <?php
  // From https://github.com/paulirish/trace.cafe/blob/main/src/app.js
  echo("<iframe id='devtools' src='https://chrome-devtools-frontend.appspot.com/serve_rev/@70f00f477937b61ba1876a1fdbf9f2e914f24fe3/worker_app.html?loadTimelineFromURL=$traceUrl' frameborder='0' style='overflow:hidden;overflow-x:hidden;overflow-y:hidden;height:100%;width:100%;position:absolute;top:0px;left:0px;right:0px;bottom:0px' height='100%' width='100%'>");
  ?>
  </iframe>
</body>
</html>

<?php
include(__DIR__ . "/include/footer.php");