# Songs

One folder per song. Everything for a song sits side by side, named `<歌手-歌名>…`:

| File | What it is |
|---|---|
| `<name>.mp3` | the song |
| `<name>.txt` | lyrics, one sung line per line |
| `<name>.lrc` | timed lyrics (edit to fix a word, then re-render) |
| `<name>.story.json` | storyboard: one shot per lyric line |
| `<name>_文案.md` | 发布标题, 备选标题, 封面短句, 文案, 话题 |
| `<name>.mp4` | the video (1920×1080, 30 fps) |
| `<name>_cover_3x4.jpg` / `_cover_4x3.jpg` | portrait / landscape covers |

Re-render any song with `python3 -m mvmaker.make_mv "songs/<name>/<name>.mp3"`.

## Index

| Song | Singer | Length | Look | Shots | 发布标题 | Notes |
|---|---|---|---|---|---|---|
| [伤心太平洋](洋澜一-伤心太平洋/) | 洋澜一 (DJ版) | 3:44 | melancholy | 48 | 我等的船还不来，我等的人还不明白 | lyrics exact |
| [你是人间四月天](解忧邵帅-你是人间四月天/) | 解忧邵帅 (Live) | 2:58 | melancholy | 37 | 愿你在我看不到的地方，安然无恙 | a few live-recording lines uncertain (see 文案 notes in chat) |
| [秋殇别恋](牙牙乐格子兮-秋殇别恋/) | 牙牙乐 / 格子兮 | 4:37 | sweet (cute) | 52 | 落叶两片三片，片片都是想你 | rap bridge (1:49–2:10) lyrics uncertain |
| [起风了](买辣椒也用券-起风了/) | 买辣椒也用券 | 5:13 | melancholy | 56 | 风吹起了从前，也吹白了你的发 | lyrics exact; a life story from the hometown station to old age |

## Earlier versions

`../archive/template-mode/` holds the first three videos, made before storyboards existed. Their scenes were picked at
random and don't follow the lyrics.

| Song | Singer | Length | Status |
|---|---|---|---|
| 失眠 | Suki刘舒妤 | 3:31 | demo remake of reference video 12 |
| 漠河舞厅 | 戴羽彤 | 3:50 | to be redone with a lyric-matched storyboard |
| 把回忆拼好给你 | DJ柚仔 remix | 6:30 | to be redone with a lyric-matched storyboard |
