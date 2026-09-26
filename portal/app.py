@@
-demo.launch(
-    server_name="0.0.0.0",
-    server_port=10000,
-    ssr_mode=False
-)
+port = int(os.getenv("PORT", "10000"))
+
+demo.launch(
+    server_name="0.0.0.0",
+    server_port=port,
+    ssr_mode=False
+)
