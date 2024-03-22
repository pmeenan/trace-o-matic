<?php
include(__DIR__ . "/include/common.php");
include(__DIR__ . "/include/header.php");
?>
<div id="test_form">
<h1>Welcome to Trace-O-Matic</h1>
<p>Trace-O-Matic automates the collection of Chromium traces on a 2023 Moto G Play using release
  builds of the latest Chromium code (within 24 hours) and, optionally, will apply a CL to the code
  and allow for testing experimental code (just be patient because that involves a build step
  that may take a while).</p>
<p>The resulting traces will be made available on a permanent, sharable URL and can be viewed in
  either the Perfetto trace viewer or Chrome's dev tools profile view.</p>
<form action="runtest.php" method="post">

  <p>
  <label for="url">Test URL:</label>
  <input type="url" id="url" name="url" size=120 value="https://www.google.com/search?q=flowers" required/>
  </p>
  <p>
  <label for="runs">Number of tests to run:</label>
  <input type="number" id="runs" name="runs" value="1" min="1" max="100" step="1" required>
  </p>
  <input type="submit" value="Start Test">
  <h3>Advanced Settings:</h3>
  <p>
  <label for="cl">Patch build with Chromium <a href="https://chromium-review.googlesource.com/">CL</a> (numeric, optional):</label>
  <input type="number" id="cl" name="cl" value="" min="5000000" max="500000000" step="1">
  </p>
  <p>
  <input type="checkbox" id="rebuild" name="rebuild" value="1">
  <label for="rebuild">Rebuild CL patch (if the CL was previously tested and has since been updated)</label>
  </p>
  <p>
  <input type="checkbox" id="clear" name="clear" value="1">
  <label for="clear">Close browser and clear profile between runs</label>
  </p>
  <p>
  <input type="checkbox" id="video" name="video" value="1">
  <label for="video">Record video of the page loading (using adb screenrecord)</label>
  </p>
  <h3>Trace Categories</h3>
  <p>
  <input type="checkbox" id="cpu" name="cpu" value="1">
  <label for="cpu">Include system CPU and scheduler tracing</label>
  </p>
  <table id="categories">
    <tr><th>Categories</th><th>High-Overhead Categories</th></tr>
    <tr>
      <td>
      <?php
      foreach($SETTINGS['trace_categories'] as $category) {
        if (!str_starts_with($category, 'disabled-by-default-')) {
          $checked = '';
          if (in_array($category, $SETTINGS['default_trace_categories'])) {
            $checked = 'checked';
          }
          $id = preg_replace('/[^A-Za-z]/', '', $category);
          echo("<input type='checkbox' id='category-$id' name='categories[]' value='$category' $checked>\n");
          echo("<label for='category-$id'>$category</label>\n<br>");
        }
      }
      ?>
      </td>
      <td>
      <?php
      foreach($SETTINGS['trace_categories'] as $category) {
        if (str_starts_with($category, 'disabled-by-default-')) {
          $checked = '';
          if (in_array($category, $SETTINGS['default_trace_categories'])) {
            $checked = 'checked';
          }
          $id = preg_replace('/[^A-Za-z]/', '', $category);
          $display = substr($category, 20);
          echo("<input type='checkbox' id='category-$id' name='categories[]' value='$category' $checked>\n");
          echo("<label for='category-$id'>$display</label>\n<br>");
        }
      }
      ?>
      </td>
    </tr>
  </table>

</form>
</div>
<?php
include(__DIR__ . "/include/footer.php");
