<?php
if (isset($ERROR)) {
  include(__DIR__ . "/error.php");
  exit(0);
}
?>
<!DOCTYPE html>
<html>
  <head>
    <title><?php echo(htmlspecialchars($TITLE)); ?></title>
    <style>
      .thumbnail {
        float: left;
        height: 200px;
        width: 150px;
      }
      .links {float: left;}
      .thumbnail img {
        height: 200px;
        max-width: 100px;
      }
      h2 {
        padding-top: 0.83em;
        margin-top: 0;
        clear: both;
      }
      .links h3 {
        text-decoration: underline;
        margin-top: 0;
      }
      .links ul {
        list-style-position: inside;
        padding-left: 1em;
      }
    </style>
    <?php
    if (isset($CSS) && strlen($CSS)) {
      echo "<style>\n$CSS\n</style>";
    }
    ?>
  </head>
  <body>
