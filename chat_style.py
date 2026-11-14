"""Independently authored, dependency-free offline presentation (no upstream assets)."""
EMOJI_ALIASES = {
    '+1': '👍', 'thumbsup': '👍', 'thumbs_up': '👍',
    '-1': '👎', 'thumbsdown': '👎', 'thumbs_down': '👎',
    'grinning': '😀', 'smiley': '😃', 'smile': '😄', 'laughing': '😆',
    'satisfied': '😆', 'joy': '😂', 'wink': '😉', 'blush': '😊',
    'heart': '❤️', 'heart_eyes': '😍', 'thinking_face': '🤔',
    'cry': '😢', 'sob': '😭', 'sunglasses': '😎', 'sweat_smile': '😅',
    'white_check_mark': '✅', 'heavy_check_mark': '✔️', 'x': '❌',
    'tada': '🎉', 'rocket': '🚀', 'fire': '🔥', 'eyes': '👀',
    'clap': '👏', 'pray': '🙏', 'raised_hands': '🙌', 'ok_hand': '👌',
    'wave': '👋', 'muscle': '💪', '100': '💯', 'star': '⭐',
    'warning': '⚠️', 'question': '❓', 'exclamation': '❗',
}


CHAT_CSS = """
:root{color-scheme:light;--lavender:#A89BBE;--beige:#D8C3A8;--ink:#302b38;--muted:#645b69;--line:#e6dfd6;--accent:#65517e}

*{box-sizing:border-box}
html{scroll-padding-top:24px}
body{margin:0;background:#f8f5f0;color:var(--ink);font:16px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
a:focus-visible,summary:focus-visible{outline:3px solid #806b9b;outline-offset:3px}
h1,h2,p{margin:0}
h1{font-size:25px;letter-spacing:-.6px}
h2{font-size:21px}
small,time,.meta{color:var(--muted)}
time{font-size:12px}
.layout{display:grid;grid-template-columns:248px minmax(0,1fr);min-height:100vh}
.sidebar{background:#eee8f2;color:#302b38;padding:30px 18px;position:sticky;top:0;height:100vh;overflow:auto}
.brand{font-size:19px;font-weight:750;padding:0 10px 27px}
.brand-icon{display:inline-grid;place-items:center;background:var(--lavender);color:#302b38;border-radius:10px;width:32px;height:32px;margin-right:7px}
.archive-label{display:block;font-size:10px;letter-spacing:2px;color:#645b69;margin-top:12px}
.team-name{font-size:12px;color:#645b69;letter-spacing:1px;padding:22px 10px 8px;overflow-wrap:anywhere}
.channel-link{display:flex;gap:8px;align-items:baseline;border-radius:7px;padding:9px 12px;color:#40364d;overflow-wrap:anywhere}
.channel-link:hover{background:#e0d6e9;text-decoration:none}
.channel-link>span{color:#776487}
.channel-link small{margin-left:auto;color:#645b69}
.sidebar-note{font-size:11px;color:#645b69;margin:36px 10px}
main{min-width:0;max-width:1250px;width:100%;margin:auto;padding:32px 46px}
.topbar{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:22px}
.eyebrow{font-size:10px;font-weight:700;letter-spacing:1.5px;color:var(--muted)}
.offline-badge{font-size:11px;color:#28745d;background:#e1f1e9;padding:5px 11px;border-radius:20px;white-space:nowrap}
.notice{color:var(--muted);font-size:12px;line-height:1.8;margin-bottom:30px}
.notice span{display:block}
section{background:white;border:1px solid var(--line);border-radius:14px;margin-bottom:30px;overflow:hidden;box-shadow:0 4px 18px #20344b05}
.channel-header{padding:24px 28px;border-bottom:1px solid var(--line);overflow-wrap:anywhere}
.channel-header h2{margin:4px 0}
.channel-header p{font-size:12px;color:var(--muted)}
.channel-header:target{background:#f2edf6}
.timeline{padding:6px 28px 26px}
.day-separator{display:flex;align-items:center;gap:14px;margin:23px 0}
.day-separator:before,.day-separator:after{content:"";height:1px;background:var(--line);flex:1}
.day-separator time{border:1px solid var(--line);border-radius:20px;padding:3px 14px;font-weight:600;background:white}
.post,.reply{display:flex;gap:13px;padding:15px 0}
.avatar{flex:0 0 38px;height:38px;border-radius:12px;display:grid;place-items:center;font-size:13px;font-weight:750;overflow:hidden}
.color-0{background:#e7dff0;color:#57436f}
.color-1{background:#eee4d7;color:#66513b}
.color-2{background:#f0e8df;color:#72563c}
.color-3{background:#e8e0ed;color:#654c78}
.color-4{background:#e4dce9;color:#5c4c70}
.color-5{background:#f2e7dd;color:#79573f}
.message{min-width:0;flex:1}
.message header{display:flex;flex-wrap:wrap;gap:5px 10px;align-items:baseline;font-size:14px;overflow-wrap:anywhere}
.message header strong{font-weight:700}
.meta{font-size:11px}
.pin{font-size:10px;color:#8c6921;background:#fff3ce;border-radius:4px;padding:1px 6px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;margin:5px 0 9px;line-height:1.7}
pre:empty{display:none}
.attachment{border:1px solid var(--line);background:#faf7f2;border-radius:9px;padding:12px 15px;margin:12px 0;max-width:480px;overflow-wrap:anywhere}
.attachment a{font-weight:600}
.attachment p{font-size:10px;color:var(--muted);margin-top:4px}
.reactions{display:flex;flex-wrap:wrap;gap:7px;margin:9px 0}
.reaction{max-width:100%;font-size:12px}
.reaction summary{display:inline-flex;align-items:center;gap:7px;border:1px solid #d7cbe3;background:#f0eaf5;border-radius:18px;padding:3px 10px;cursor:pointer;overflow-wrap:anywhere}
.reaction summary::-webkit-details-marker{display:none}
.reaction summary span[role]{font-size:17px}
.reaction ul{margin:8px 0;padding:10px 12px 10px 28px;background:#f6f1f8;border-radius:8px;overflow-wrap:anywhere}
.thread-toggle{cursor:pointer;color:var(--accent);font-size:12px;font-weight:600;margin:12px 0}
.thread{border-left:2px solid var(--beige);padding-left:16px;background:#faf7f2;border-radius:0 8px 8px 0}
.reply{padding-right:12px}
.reply .avatar{flex-basis:30px;height:30px;border-radius:9px;font-size:11px}
.empty-state{text-align:center;padding:48px 10px;color:var(--muted)}
footer{text-align:center;font-size:11px;color:var(--muted);padding:10px 0 24px}
.sr-only,.skip-link:not(:focus){position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.skip-link:focus{display:block;padding:10px;background:white}

@media(max-width:900px){.layout{grid-template-columns:200px minmax(0,1fr)}
main{padding:24px}
.timeline{padding:4px 18px 20px}
.channel-header{padding:20px}
}

@media(max-width:640px){.layout{display:block}
.sidebar{position:static;height:auto;padding:18px}
.brand{padding:0 4px 10px}
.archive-label{display:inline;margin-left:10px;letter-spacing:1px}
.sidebar nav{max-height:180px;overflow:auto}
.team-name{padding-top:12px}
.channel-link{padding:6px 10px}
.sidebar-note{margin:12px 4px 0}
main{padding:22px 12px}
.topbar{gap:8px}
h1{font-size:22px}
.eyebrow{letter-spacing:.8px;font-size:9px}
.notice{margin-bottom:20px}
.timeline{padding:4px 12px 16px}
.post,.reply{gap:8px}
.avatar{flex-basis:30px;height:30px;border-radius:9px}
.thread{padding-left:8px}
.reply .avatar{display:none}
.reply{padding-right:4px}
.channel-header{padding:18px}
.reaction ul{padding-left:20px}
}

@media print{.layout{display:block}
.sidebar,.skip-link{display:none}
main{max-width:none;padding:0}
section{box-shadow:none}
details{break-inside:avoid}
}

"""
