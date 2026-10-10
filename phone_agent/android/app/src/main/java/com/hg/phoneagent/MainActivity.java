package com.hg.phoneagent;

import android.app.Activity;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.view.View;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.graphics.Color;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import org.json.*;
import javax.net.ssl.SSLSocketFactory;
import javax.net.ssl.SSLSocket;

public class MainActivity extends Activity {
    SharedPreferences prefs; EditText server, pairing; TextView status; WebView web; Button connect;
    String deviceId;
    final Handler main = new Handler(Looper.getMainLooper());
    volatile boolean running=false; Socket ws;

    @Override public void onCreate(Bundle b){super.onCreate(b); prefs=getSharedPreferences("hg",0); deviceId=prefs.getString("device_id", "hg-"+UUID.randomUUID().toString()); prefs.edit().putString("device_id",deviceId).apply(); build();}
    void build(){
        LinearLayout root=new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL); int sbRes=getResources().getIdentifier("status_bar_height","dimen","android"); int sb=sbRes>0?getResources().getDimensionPixelSize(sbRes):0; root.setPadding(0,sb,0,0); root.setBackgroundColor(Color.rgb(15,17,23));
        server=new EditText(this); server.setHint("https://<HG endpoint>"); server.setText(prefs.getString("server", "")); server.setTextColor(Color.WHITE); server.setHintTextColor(Color.GRAY); root.addView(server);
        pairing=new EditText(this); pairing.setHint("Pairing token (chỉ lần đầu)"); pairing.setTextColor(Color.WHITE); pairing.setHintTextColor(Color.GRAY); root.addView(pairing);
        connect=new Button(this); connect.setText("Kết nối HG"); root.addView(connect);
        status=new TextView(this); status.setTextColor(Color.LTGRAY); status.setText("Chưa kết nối • "+deviceId); root.addView(status);
        web=new WebView(this); web.setVisibility(View.GONE); WebSettings wsx=web.getSettings(); wsx.setJavaScriptEnabled(true); wsx.setDomStorageEnabled(true); web.setWebViewClient(new WebViewClient()); root.addView(web,new LinearLayout.LayoutParams(-1,0,1));
        setContentView(root); connect.setOnClickListener(v->new Thread(this::connectFlow).start());
        if(!server.getText().toString().isEmpty()) new Thread(this::connectFlow).start();
    }
    void ui(String s){main.post(()->{status.setText(s);status.setVisibility(s!=null&&s.contains("CONNECTED")?View.GONE:View.VISIBLE);});}
    String base(){String s=server.getText().toString().trim(); if(s.endsWith("/"))s=s.substring(0,s.length()-1); return s;}
    void connectFlow(){try{
        String base=base(); if(base.isEmpty())throw new Exception("Thiếu server URL"); if(!base.startsWith("https://"))throw new Exception("PHONE_AGENT_REQUIRES_HTTPS"); prefs.edit().putString("server",base).apply();
        String token=prefs.getString("device_token","");
        if(token.isEmpty()){String pair=pairing.getText().toString().trim(); if(pair.isEmpty()){try{pair=new String(openFileInput("pairing.txt").readAllBytes(),StandardCharsets.UTF_8).trim();}catch(Exception ignored){}}
            JSONObject body=new JSONObject(); body.put("pairing_token",pair); body.put("device_id",deviceId); body.put("name","HG Phone"); body.put("platform","android"); body.put("capabilities",new JSONArray(Arrays.asList("ping","device_info","termux_command")));
            JSONObject r=post(base+"/api/phone/register",body); token=r.getString("device_token"); prefs.edit().putString("device_token",token).apply(); main.post(()->pairing.setText(""));
        }
        ui("Đã đăng ký • mở HG…"); openWeb(base); running=true; startLongPoll(base,token);
    }catch(Exception e){ui("Kết nối lỗi: "+e.getMessage());}}
    void openWeb(String base){main.post(()->{web.setVisibility(View.VISIBLE); web.loadUrl(base+"/"); connect.setVisibility(View.GONE); server.setVisibility(View.GONE); pairing.setVisibility(View.GONE);});}
    JSONObject post(String url, JSONObject body)throws Exception{HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection(); c.setRequestMethod("POST"); c.setConnectTimeout(10000); c.setReadTimeout(15000); c.setDoOutput(true); c.setRequestProperty("Content-Type","application/json"); try(OutputStream o=c.getOutputStream()){o.write(body.toString().getBytes(StandardCharsets.UTF_8));} int code=c.getResponseCode(); InputStream in=code<400?c.getInputStream():c.getErrorStream(); String text=new String(in.readAllBytes(),StandardCharsets.UTF_8); if(code>=400)throw new Exception(text); return new JSONObject(text);}
    void handleMessage(OutputStream out,String text)throws Exception{JSONObject m=new JSONObject(text); if("hello".equals(m.optString("type"))){sendText(out,"{\"type\":\"heartbeat\"}");return;} if("command".equals(m.optString("type"))){String id=m.optString("id");JSONObject c=m.optJSONObject("command");JSONObject result=new JSONObject(); result.put("ok",true); String type=c==null?"":c.optString("type"); if("ping".equals(type))result.put("pong",true); else if("device_info".equals(type)){result.put("device_id",deviceId);result.put("model",android.os.Build.MODEL);result.put("android",android.os.Build.VERSION.RELEASE);} else if("termux_command".equals(type)){String path=c.optString("path"); if(!"/data/data/com.termux/files/home/hg-agent/dispatch.sh".equals(path)){result.put("ok",false);result.put("error","CAPABILITY_DENIED");} else {JSONArray a=c.optJSONArray("args"); String[] args=new String[a==null?0:a.length()]; for(int i=0;i<args.length;i++)args[i]=a.optString(i); String rid=TermuxRunner.run(this,path,args); result.put("accepted",true); result.put("termux_request_id",rid); watchTermuxResult(out,id,rid);}} else {result.put("ok",false);result.put("error","UNSUPPORTED_COMMAND");} JSONObject r=new JSONObject();r.put("type","result");r.put("id",id);r.put("kind","phone.command.result");r.put("result",result);sendText(out,r.toString());}}
    void watchTermuxResult(OutputStream out,String commandId,String requestId){new Thread(()->{long deadline=System.currentTimeMillis()+60000; while(System.currentTimeMillis()<deadline){TermuxResultCache.Result tr=TermuxResultCache.take(requestId); if(tr!=null){try{JSONObject result=new JSONObject(); result.put("ok",tr.exitCode==0); result.put("exit_code",tr.exitCode); result.put("stdout_digest",sha256(tr.stdout==null?"":tr.stdout)); result.put("stderr_digest",sha256(tr.stderr==null?"":tr.stderr)); JSONObject r=new JSONObject(); r.put("type","result"); r.put("id",commandId); r.put("kind","phone.command.result"); r.put("result",result); synchronized(out){sendText(out,r.toString());} }catch(Exception ignored){} return;} try{Thread.sleep(250);}catch(InterruptedException e){Thread.currentThread().interrupt();return;}}} ).start();}
    String sha256(String s)throws Exception{MessageDigest d=MessageDigest.getInstance("SHA-256"); byte[] b=d.digest(s.getBytes(StandardCharsets.UTF_8)); StringBuilder h=new StringBuilder(); for(byte x:b)h.append(String.format("%02x",x)); return h.toString();}
    byte[] randomBytes(int n){byte[] b=new byte[n];new Random().nextBytes(b);return b;}
    void readHandshake(InputStream in)throws Exception{ByteArrayOutputStream b=new ByteArrayOutputStream();int prev=0,cur;while((cur=in.read())!=-1){b.write(cur);if(prev=='\r'&&cur=='\n'){byte[] a=b.toByteArray();int n=a.length;if(n>=4&&a[n-4]=='\r'&&a[n-3]=='\n')break;}prev=cur;}String h=b.toString(StandardCharsets.US_ASCII);if(!h.startsWith("HTTP/1.1 101"))throw new Exception("WebSocket handshake failed: "+h.split("\r\n")[0]);}
    void sendText(OutputStream out,String s)throws Exception{sendFrame(out,(byte)1,s.getBytes(StandardCharsets.UTF_8));}
    void sendFrame(OutputStream out,byte opcode,byte[] data)throws Exception{int n=data.length;ByteArrayOutputStream h=new ByteArrayOutputStream();h.write(0x80|opcode);if(n<126)h.write(0x80|n);else if(n<65536){h.write(0x80|126);h.write((n>>8)&255);h.write(n&255);}else{h.write(0x80|127);for(int i=7;i>=0;i--)h.write((n>>(8*i))&255);}byte[] mask=randomBytes(4);h.write(mask);for(int i=0;i<n;i++)data[i]^=mask[i%4];h.write(data);out.write(h.toByteArray());out.flush();}
    Frame readFrame(InputStream in)throws Exception{int a=in.read(),b=in.read();if(a<0||b<0)return null;int op=a&15;int n=b&127;if(n==126)n=(in.read()<<8)|in.read();else if(n==127){n=0;for(int i=0;i<8;i++)n=(n<<8)|in.read();}boolean masked=(b&128)!=0;byte[] mask=masked?in.readNBytes(4):new byte[0];byte[] d=in.readNBytes(n);if(masked)for(int i=0;i<n;i++)d[i]^=mask[i%4];return new Frame(op,d);}
    static class Frame{int opcode;byte[] data;Frame(int o,byte[]d){opcode=o;data=d;}}
    @Override protected void onDestroy(){running=false;try{if(ws!=null)ws.close();}catch(Exception ignored){}super.onDestroy();}

    // ---- LONGPOLL_HTTPS_V2: thay hoàn toàn luồng WSS của V1 ----
    LongPollClient poller;
    void startLongPoll(final String base, final String token){
        poller = new LongPollClient(base, token, (capability, params) -> {
            JSONObject req = new JSONObject();
            req.put("request_id", params.optString("request_id", ""));
            req.put("capability", capability);
            req.put("params", params);
            JSONObject r = TermuxDispatch.dispatch(this, req, 60000L);
            return r.optJSONObject("result") != null ? r.getJSONObject("result") : r;
        });
        new Thread(() -> poller.runLoop()).start();
    }
    @Override protected void onDestroy(){
        super.onDestroy();
        running = false;
        if (poller != null) poller.stop();
    }
}
