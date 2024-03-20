<?php
include(__DIR__ . "/include/common.php");
if (isset($ID) && isset($RUN)) {
  $TITLE = "$ID.$RUN Trace : Trace-O-Matic";
  $traceUrl = $TEST_PATH . sprintf("%03d-trace.perfetto.gz", $RUN);
  if (!is_file(__DIR__ . $traceUrl)) {
    $ERROR = "Trace not found";
  }
} else {
  $ERROR = "Invalid trace";
}
$CSS = "body {margin:0px;padding:0px;overflow:hidden}\n";
include(__DIR__ . "/include/header.php");
?>
  <script>
    async function PerfettoLoaded() {
      <?php
      echo "const traceUrl = new URL('$traceUrl', window.location).href;\n";
      ?>
      const resp = await fetch(traceUrl);
      const blob = await resp.blob();
      const arrayBuffer = await blob.arrayBuffer();
      const ORIGIN = 'https://ui.perfetto.dev';
      document.getElementById('perfetto').contentWindow.postMessage({
            perfetto: {
                buffer: arrayBuffer,
                title: 'Trace-O-Matic Trace',
                url: window.location.toString(),
            }}, ORIGIN);
    }
  </script>
  <iframe id="perfetto" src="https://ui.perfetto.dev" frameborder="0" style="overflow:hidden;overflow-x:hidden;overflow-y:hidden;height:100%;width:100%;position:absolute;top:0px;left:0px;right:0px;bottom:0px" height="100%" width="100%" onload="PerfettoLoaded();">
  </iframe>
</body>
</html>

<?php
include(__DIR__ . "/include/footer.php");