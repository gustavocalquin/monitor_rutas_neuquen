package ar.com.climaenruta.neuquen;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.*;
import android.content.Intent;
import android.net.Uri;
import android.graphics.Color;
import android.view.View;
import java.net.HttpURLConnection;
import java.net.URL;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.*;
import org.json.JSONObject;

public class MainActivity extends Activity {
    private WebView web;
    private final ExecutorService network = Executors.newFixedThreadPool(4);
    private volatile boolean closed;
    private static final String ROAD_URL = "https://w2.dpvneuquen.gov.ar/ParteDiario.csv";
    private static final String CACHE_URL = "https://raw.githubusercontent.com/gustavocalquin/monitor_rutas_neuquen/main/cache/ParteDiario.csv";

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        web = new WebView(this);
        web.setBackgroundColor(Color.rgb(246,245,239));
        web.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                            insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets.consumeSystemWindowInsets();
        });
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSupportMultipleWindows(false);
        settings.setSafeBrowsingEnabled(true);
        web.addJavascriptInterface(new Bridge(), "AndroidApp");
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return true; // Only the bundled document is allowed inside the bridge-enabled view.
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                return new WebResourceResponse("text/plain", "UTF-8", new ByteArrayInputStream(new byte[0]));
            }
        });
        setContentView(web);
        try (InputStream input = getAssets().open("index.html")) {
            web.loadDataWithBaseURL("https://clima.local/", read(input, 3000000), "text/html", "UTF-8", null);
        } catch (Exception e) {
            android.widget.TextView error = new android.widget.TextView(this);
            error.setText("No se pudo abrir Clima en Ruta. Volvé a instalar la aplicación.");
            setContentView(error);
        }
    }

    private static String read(InputStream input, int limit) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192]; int count;
        while ((count = input.read(buffer)) != -1) {
            if (out.size() + count > limit) throw new IOException("Respuesta demasiado grande");
            out.write(buffer, 0, count);
        }
        byte[] data = out.toByteArray();
        try {
            return StandardCharsets.UTF_8.newDecoder().decode(java.nio.ByteBuffer.wrap(data)).toString();
        } catch (java.nio.charset.CharacterCodingException e) {
            return new String(data, java.nio.charset.Charset.forName("windows-1252"));
        }
    }

    private String get(String address) throws IOException {
        HttpURLConnection connection = (HttpURLConnection) new URL(address).openConnection();
        try {
            connection.setConnectTimeout(12000);
            connection.setReadTimeout(15000);
            connection.setInstanceFollowRedirects(false);
            connection.setRequestProperty("User-Agent", "Clima-en-Ruta-Neuquen-Android/1.0");
            if (connection.getResponseCode() != 200) throw new IOException("HTTP " + connection.getResponseCode());
            try (InputStream input = connection.getInputStream()) { return read(input, 2000000); }
        } finally { connection.disconnect(); }
    }

    private void send(String type, int request, String key, String body, String source, String error) {
        try {
            JSONObject message = new JSONObject();
            message.put("type", type); message.put("request", request); message.put("key", key);
            message.put("body", body); message.put("source", source); message.put("error", error);
            String script = "window.receiveNative(" + message.toString() + ");";
            runOnUiThread(() -> { if (!closed) web.evaluateJavascript(script, null); });
        } catch (Exception ignored) { }
    }

    public class Bridge {
        @JavascriptInterface public void roads(int request) {
            network.execute(() -> {
                for (String address : new String[]{ROAD_URL, CACHE_URL}) {
                    try {
                        String csv = get(address);
                        if (!csv.substring(0, Math.min(csv.length(), 700)).contains("CodigoTramo"))
                            throw new IOException("Formato inesperado");
                        send("roads", request, "", csv, address.equals(ROAD_URL) ? "Vialidad Provincial" : "Copia de GitHub", "");
                        return;
                    } catch (Exception ignored) { }
                }
                String saved = getPreferences(MODE_PRIVATE).getString("roads", "");
                send("roads", request, "", saved, "Última copia del teléfono",
                     "No se pudo descargar el parte. Se revisó la última copia disponible.");
            });
        }

        @JavascriptInterface public void saveRoads(String csv) {
            if (csv != null && csv.length() < 1000000)
                getPreferences(MODE_PRIVATE).edit().putString("roads", csv).apply();
        }

        @JavascriptInterface public void weather(int request, String code, double lat, double lon) {
            if (!Double.isFinite(lat) || !Double.isFinite(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) return;
            network.execute(() -> {
                String url = "https://api.open-meteo.com/v1/forecast?latitude=" + lat + "&longitude=" + lon
                    + "&timezone=America%2FArgentina%2FBuenos_Aires&forecast_days=2"
                    + "&current=temperature_2m,precipitation,rain,snowfall,weather_code,wind_speed_10m,wind_gusts_10m"
                    + "&hourly=temperature_2m,precipitation,rain,snowfall,weather_code,wind_speed_10m,wind_gusts_10m,visibility";
                try { send("weather", request, code, get(url), "Open-Meteo", ""); }
                catch (Exception e) { send("weather", request, code, "", "Open-Meteo", "No se pudo consultar el clima en este punto."); }
            });
        }

        @JavascriptInterface public void openLink(String address) {
            String[] allowed = {"https://www.dpvneuquen.gov.ar/", "https://w2.dpvneuquen.gov.ar/ParteDiario.pdf",
                "https://www.argentina.gob.ar/transporte/vialidad-nacional/estado-de-rutas",
                "https://www.smn.gob.ar/alertas", "https://whatsapp.com/channel/0029Vakr9GiIyPtaTYFeIe2J"};
            for (String url : allowed) if (url.equals(address)) {
                runOnUiThread(() -> {
                    try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(address))); }
                    catch (Exception e) { android.widget.Toast.makeText(MainActivity.this, "No hay una aplicación para abrir el enlace", android.widget.Toast.LENGTH_SHORT).show(); }
                });
                return;
            }
        }
    }

    @Override public void onBackPressed() {
        web.evaluateJavascript("window.closePicker ? window.closePicker() : false", handled -> {
            if (!"true".equals(handled)) finish();
        });
    }
    @Override protected void onDestroy() {
        closed = true; network.shutdownNow(); web.removeJavascriptInterface("AndroidApp"); web.destroy();
        super.onDestroy();
    }
}
