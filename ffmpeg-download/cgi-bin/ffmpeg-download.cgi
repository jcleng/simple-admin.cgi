#!/bin/sh

# ========== 基础配置 ==========
USER="${FFMPEG_USER:-admin}"
PASS="${FFMPEG_PASS:-admin}"
COOKIE_NAME="ffdl"
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$SCRIPT_DIR")
DL_DIR="${FFMPEG_DL_DIR:-$ROOT/downloads}"
chmod 777 "$ROOT" 2>/dev/null
mkdir -p "$DL_DIR"
chmod 777 "$DL_DIR" 2>/dev/null
if [ -d "$DL_DIR" ] && [ -w "$DL_DIR" ]; then
    DLOK=1
else
    DLOK=0
fi

case "$DL_DIR" in
    "$ROOT"/*) DL_WEB="/${DL_DIR#"$ROOT/"}" ;;
    *) DL_WEB="/downloads" ;;
esac

# ========== HTTP 工具函数 ==========
header() {
    printf "Content-Type: text/html; charset=utf-8\r\n\r\n"
}

redirect() {
    printf "Status: 302 Found\r\nLocation: %s\r\n\r\n" "$1"
    exit 0
}

html_escape() {
    sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g; s/"/\&quot;/g'
}

urldecode() {
    printf '%s' "$1" | awk '
    function hx(c,  v) {
        if (c ~ /^[0-9]$/) return c + 0
        if (c ~ /^[a-f]$/) return 10 + index("abcdef", c) - 1
        if (c ~ /^[A-F]$/) return 10 + index("ABCDEF", c) - 1
        return -1
    }
    {
        n = length($0)
        for (i = 1; i <= n; i++) {
            c = substr($0, i, 1)
            if (c == "+") { printf " "; continue }
            if (c == "%" && i + 2 <= n) {
                hi = hx(substr($0, i + 1, 1))
                lo = hx(substr($0, i + 2, 1))
                if (hi >= 0 && lo >= 0) {
                    printf "%c", hi * 16 + lo
                    i += 2
                    continue
                }
            }
            printf "%s", c
        }
    }'
}

# ========== Cookie / Auth ==========
COOKIE=$(echo "$HTTP_COOKIE" | tr ';' '\n' | grep "${COOKIE_NAME}=" | cut -d= -f2-)
AUTH_OK=0

if [ "$COOKIE" = "$(echo -n "$USER$PASS" | md5sum | cut -c1-32)" ]; then
    AUTH_OK=1
fi

# ========== 登录处理 ==========
if [ "$AUTH_OK" -eq 0 ]; then
    if [ "$REQUEST_METHOD" = "POST" ]; then
        POST_DATA=$(dd bs=1 count="${CONTENT_LENGTH:-0}" 2>/dev/null)
        U=$(echo "$POST_DATA" | sed 's/.*u=\([^&]*\).*/\1/')
        P=$(echo "$POST_DATA" | sed 's/.*p=\([^&]*\).*/\1/')

        if [ "$U" = "$USER" ] && [ "$P" = "$PASS" ]; then
            HASH=$(echo -n "$USER$PASS" | md5sum | cut -c1-32)
            printf "Status: 302 Found\r\n"
            printf "Set-Cookie: %s=%s; Path=/\r\n" "$COOKIE_NAME" "$HASH"
            printf "Location: /cgi-bin/ffmpeg-download.cgi\r\n\r\n"
            exit 0
        fi
        ERR="Invalid credentials"
    fi

    header
    cat <<EOF
<!doctype html>
<html><head><meta charset="utf-8"><title>FFmpeg Download Login</title></head>
<body style="font-family:system-ui;display:flex;justify-content:center;align-items:center;height:100vh;background:#f5f5f5">
<form method="post" style="background:#fff;padding:20px;border-radius:8px;width:280px;box-shadow:0 2px 8px rgba(0,0,0,.1)">
<h3>FFmpeg 视频下载登录</h3>
$([ -n "$ERR" ] && echo "<p style='color:red'>$ERR</p>")
<input name="u" placeholder="Username" required style="width:100%;margin-bottom:10px;padding:8px">
<input name="p" type="password" placeholder="Password" required style="width:100%;margin-bottom:10px;padding:8px">
<button style="width:100%;padding:8px;background:#007bff;color:#fff;border:none;cursor:pointer">Login</button>
</form>
</body></html>
EOF
    exit 0
fi

# ========== 退出 ==========
if echo "$QUERY_STRING" | grep -q "logout"; then
    printf "Status: 302 Found\r\n"
    printf "Set-Cookie: %s=; Path=/; Max-Age=0\r\n" "$COOKIE_NAME"
    printf "Location: /cgi-bin/ffmpeg-download.cgi\r\n\r\n"
    exit 0
fi

# ========== 读取请求参数 ==========
if [ "$REQUEST_METHOD" = "POST" ]; then
    POST_DATA=$(dd bs=1 count="${CONTENT_LENGTH:-0}" 2>/dev/null)
    INPUT="$POST_DATA"
else
    INPUT="$QUERY_STRING"
fi

# ========== 删除任务 ==========
case "$QUERY_STRING" in
    *"act=delete"*)
        DEL=$(echo "$QUERY_STRING" | sed 's/.*name=\([^&]*\).*/\1/')
        DEL=$(urldecode "$DEL" | sed 's/[^A-Za-z0-9._-]/_/g')
        case "$DEL" in
            ""|.|..)
                redirect "/cgi-bin/ffmpeg-download.cgi?msg=invalid"
                ;;
            *)
                if [ -f "$DL_DIR/$DEL.prog" ]; then
                    redirect "/cgi-bin/ffmpeg-download.cgi?msg=busy"
                fi
                rm -f "$DL_DIR/$DEL.mp4" "$DL_DIR/$DEL.jpg" "$DL_DIR/$DEL.prog" \
                      "$DL_DIR/$DEL.log" "$DL_DIR/$DEL.sec" "$DL_DIR/$DEL.done" "$DL_DIR/$DEL.failed"
                redirect "/cgi-bin/ffmpeg-download.cgi?msg=deleted&name=$DEL"
                ;;
        esac
        ;;
esac

# ========== 提交下载任务 ==========
if echo "$INPUT" | grep -q 'url='; then
    if [ "$DLOK" -ne 1 ]; then
        redirect "/cgi-bin/ffmpeg-download.cgi?msg=nodir"
    fi

    URLRAW=$(echo "$INPUT" | sed 's/.*url=\([^&]*\).*/\1/')
    URL=$(urldecode "$URLRAW" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')

    case "$URL" in
        http://*|https://*) ;;
        *) redirect "/cgi-bin/ffmpeg-download.cgi?msg=invalid" ;;
    esac

    NAME=$(printf '%s' "$URL" | sed 's/\?.*//' | sed 's#.*/##' | sed 's/[^A-Za-z0-9._-]/_/g')
    NAME=${NAME%.*}
    NAME=$(printf '%s' "$NAME" | sed 's/[^A-Za-z0-9._-]/_/g')

    case "$NAME" in
        ""|.|..) redirect "/cgi-bin/ffmpeg-download.cgi?msg=invalid" ;;
    esac

    if [ -f "$DL_DIR/$NAME.prog" ]; then
        redirect "/cgi-bin/ffmpeg-download.cgi?msg=active"
    fi

    cat >"$DL_DIR/.w.sh" <<'WORKEREOF'
#!/bin/sh
URL="$1"
NAME="$2"
DIR="$3"
[ -d "$DIR" ] || exit 1
rm -f "$DIR/$NAME.done" "$DIR/$NAME.failed" "$DIR/$NAME.jpg" "$DIR/$NAME.log" "$DIR/$NAME.sec"
touch "$DIR/$NAME.log"

DUR=$(ffmpeg -nostdin -i "$URL" 2>&1 | grep -o 'Duration: [0-9][0-9]:[0-9][0-9]:[0-9][0-9.]*' | head -1 | cut -d' ' -f2)
[ -n "$DUR" ] && echo "$DUR" | awk -F: '{ printf "%.3f", $1*3600+$2*60+$3 }' > "$DIR/$NAME.sec"

ffmpeg -nostdin -y -i "$URL" -c copy -progress "$DIR/$NAME.prog" "$DIR/$NAME.mp4" >>"$DIR/$NAME.log" 2>&1
if [ $? -ne 0 ]; then
    rm -f "$DIR/$NAME.prog" "$DIR/$NAME.mp4"
    touch "$DIR/$NAME.failed"
    exit 1
fi

DUR=$(cat "$DIR/$NAME.sec" 2>/dev/null)
case "$DUR" in
    ""|0|0.000)
        DUR=$(ffmpeg -nostdin -i "$DIR/$NAME.mp4" 2>&1 | grep -o 'Duration: [0-9][0-9]:[0-9][0-9]:[0-9][0-9.]*' | head -1 | cut -d' ' -f2 | awk -F: '{ printf "%.3f", $1*3600+$2*60+$3 }')
        ;;
esac
case "$DUR" in
    ""|0|0.000) INTERVAL=10 ;;
    *) INTERVAL=$(awk -v d="$DUR" 'BEGIN{ i=(d/54)*0.97; if (i<0.05) i=0.05; printf "%.3f", i }') ;;
esac

ffmpeg -nostdin -y -i "$DIR/$NAME.mp4" -vf "fps=1/$INTERVAL,scale=160:-2,tile=6x9" -frames:v 1 -q:v 3 -an "$DIR/$NAME.jpg" >>"$DIR/$NAME.log" 2>&1

rm -f "$DIR/$NAME.prog"
touch "$DIR/$NAME.done"
exit 0
WORKEREOF
    chmod +x "$DL_DIR/.w.sh"

    : > "$DL_DIR/$NAME.prog"
    nohup sh "$DL_DIR/.w.sh" "$URL" "$NAME" "$DL_DIR" >/dev/null 2>&1 &
    redirect "/cgi-bin/ffmpeg-download.cgi?msg=started"
fi

# ========== 消息映射 ==========
MSGWORD=""
case "$(echo "$QUERY_STRING" | sed 's/.*msg=\([^&]*\).*/\1/')" in
    started)  MSGWORD="下载任务已在后台启动，请稍候刷新查看进度" ;;
    invalid)  MSGWORD="请输入有效的视频 URL 地址" ;;
    nodir)    MSGWORD="下载目录不可写（$DL_DIR），无法开始下载" ;;
    active)   MSGWORD="该任务正在下载中，请勿重复提交" ;;
    busy)     MSGWORD="任务正在下载中，无法删除" ;;
    deleted)  MSGWORD="已删除该任务" ;;
esac

# ========== 收集任务列表 ==========
TASKS=""
for f in "$DL_DIR"/*; do
    [ -f "$f" ] || continue
    case "$f" in
        *.mp4|*.prog|*.failed|*.done)
            b=${f##*/}
            b=${b%.*}
            TASKS="$TASKS$b\n"
            ;;
    esac
done
TASKS=$(printf "%b" "$TASKS" | sort -u)

# ========== 主页面 ==========
header
cat <<EOF
<!doctype html>
<html><head><meta charset="utf-8"><title>FFmpeg 视频下载</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="4">
<style>
body{font-family:system-ui;padding:20px;background:#f7f7f7;max-width:980px;margin:0 auto}
.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:15px}
.card{background:#fff;border-radius:8px;padding:16px;margin-bottom:15px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
input[type=text]{width:72%;padding:9px;border:1px solid #ccc;border-radius:4px;box-sizing:border-box}
button{padding:9px 22px;background:#007bff;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:14px}
.msg{background:#d4edda;color:#155724;padding:8px 12px;border-radius:4px;margin-bottom:15px}
table{width:100%;border-collapse:collapse;background:#fff}
th,td{padding:10px;border-bottom:1px solid #eee;text-align:left;vertical-align:top}
a{text-decoration:none;padding:4px 8px;border-radius:4px;font-size:12px;margin-right:4px}
.del{background:#dc3545;color:#fff}.dl{background:#28a745;color:#fff}
.logout{background:#343a40;color:#fff;padding:6px 12px;border-radius:4px}
.bar{height:10px;background:#eee;border-radius:5px;width:220px;overflow:hidden}
.fill{height:100%;background:#28a745}
.pct{font-weight:bold;color:#155724}
.run{background:#f0f9ff;color:#0c5460}
.ok{background:#d4edda;color:#155724}
.bad{background:#f8d7da;color:#721c24}
.pv{width:160px;height:90px;object-fit:cover;border-radius:4px;border:1px solid #ddd}
code{background:#f1f1f1;padding:2px 5px;border-radius:3px;font-size:12px;word-break:break-all}
sub{color:#888}
</style>
</head>
<body>
<div class="topbar">
<h2>FFmpeg 视频下载</h2>
<a class="logout" href="/cgi-bin/ffmpeg-download.cgi?logout">Logout</a>
</div>
$([ -n "$MSGWORD" ] && echo "<div class='msg'>$MSGWORD</div>")
<div class="card">
<form method="post" action="/cgi-bin/ffmpeg-download.cgi">
<input type="text" name="url" placeholder="输入视频 url 地址，例如 https://example.com/video.mp4" required>
<button type="submit">开始下载</button>
<sub>下载到 $DL_DIR</sub>
</form>
</div>
<div class="card">
<table>
<tr><th>文件</th><th>状态</th><th>进度</th><th>预览</th><th>操作</th></tr>
EOF

if [ -z "$TASKS" ]; then
    echo "<tr><td colspan='5'>暂无任务</td></tr>"
fi

for NAME in $TASKS; do
    STATUS="unknown"
    [ -f "$DL_DIR/$NAME.done" ] && STATUS="done"
    [ -f "$DL_DIR/$NAME.failed" ] && STATUS="failed"
    [ -f "$DL_DIR/$NAME.prog" ] && STATUS="downloading"

    PCT=""
    META=""
    SIZE=""
    if [ "$STATUS" = "downloading" ]; then
        PROGF="$DL_DIR/$NAME.prog"
        MS=$(grep '^out_time_ms=' "$PROGF" | tail -1 | cut -d= -f2)
        OT=$(grep '^out_time=' "$PROGF" | tail -1 | cut -d= -f2)
        SP=$(grep '^speed=' "$PROGF" | tail -1 | cut -d= -f2)
        TS=$(grep '^total_size=' "$PROGF" | tail -1 | cut -d= -f2)
        DURV=$(cat "$DL_DIR/$NAME.sec" 2>/dev/null)
        if [ -n "$MS" ] && [ "$MS" != "N/A" ] && [ -n "$DURV" ] && [ "$DURV" != "0.000" ] && [ "$DURV" != "0" ]; then
            PCT=$(awk -v ms="$MS" -v d="$DURV" 'BEGIN{p=ms/1000/d*100; if(p<0)p=0; if(p>100)p=100; printf "%.1f", p}')
        fi
        [ -n "$OT" ] && META="已处理 $OT"
        [ -n "$SP" ] && META="$META 速度 $SP"
        [ -n "$TS" ] && [ "$TS" != "N/A" ] && SIZE=$(awk -v t="$TS" 'BEGIN{printf "%.1f", t/1048576}')
        [ -n "$SIZE" ] && META="$META 大小 ${SIZE}MB"
    fi

    ESC=$(echo "$NAME" | html_escape)

    case "$STATUS" in
        downloading) SCODE="run"; STXT="下载中" ;;
        done)        SCODE="ok";  STXT="已完成" ;;
        failed)      SCODE="bad"; STXT="失败" ;;
        *)           SCODE="";    STXT="未知" ;;
    esac

    echo "<tr>"
    echo "<td><code>$ESC</code></td>"
    echo "<td><span class='$SCODE' style='padding:3px 8px;border-radius:4px'>$STXT</span></td>"
    if [ -n "$PCT" ]; then
        echo "<td><div class='pct'>$PCT%</div><div class='bar'><div class='fill' style='width:$PCT%'></div></div>$([ -n "$META" ] && echo "<sub>$META</sub>")</td>"
    elif [ "$STATUS" = "done" ]; then
        echo "<td><sub>精灵图已生成 (6x9)</sub></td>"
    else
        echo "<td>$([ -n "$META" ] && echo "<sub>$META</sub>")</td>"
    fi
    if [ "$STATUS" = "done" ] && [ -f "$DL_DIR/$NAME.jpg" ]; then
        echo "<td><a href=\"${DL_WEB}/$ESC.jpg\" target=\"_blank\"><img class=\"pv\" src=\"${DL_WEB}/$ESC.jpg\" alt=\"preview\"></a></td>"
    elif [ -f "$DL_DIR/$NAME.mp4" ]; then
        echo "<td><sub>生成中...</sub></td>"
    else
        echo "<td><sub>-</sub></td>"
    fi
    echo "<td>"
    if [ -f "$DL_DIR/$NAME.mp4" ]; then
        echo "<a class=\"dl\" href=\"${DL_WEB}/$ESC.mp4\">下载视频</a>"
    fi
    if [ "$STATUS" != "downloading" ]; then
        echo "<a class=\"del\" href=\"/cgi-bin/ffmpeg-download.cgi?act=delete&name=$ESC\" onclick=\"return confirm('删除 $ESC 的所有文件?')\">删除</a>"
    fi
    echo "</td>"
    echo "</tr>"
done

echo "</table></div></body></html>"