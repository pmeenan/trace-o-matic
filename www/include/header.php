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
  </head>
  <body>
