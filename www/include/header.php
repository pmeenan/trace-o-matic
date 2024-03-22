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
      body {
        font-family: Arial, sans-serif;
      }
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
      #test_form {
        margin: auto;
        max-width: 1000px;
      }
      #test_form form {
        padding-left: 40px;
      }
      #categories {
        text-align: left;
        border-collapse: collapse;
        margin: 1em;
        border-style: solid;
      }
      #categories tr {
        border-style: solid;
      }
      #categories th {
        border-style: solid;
      }
      #categories td {
        border-style: solid;
        vertical-align: top;
      }
    </style>
    <?php
    if (isset($CSS) && strlen($CSS)) {
      echo "<style>\n$CSS\n</style>";
    }
    ?>
  </head>
  <body>
