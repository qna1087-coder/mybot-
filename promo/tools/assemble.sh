#!/usr/bin/env bash
# Join the rendered chunks, lay the soundtrack under them and package the deliverables.
#   tools/assemble.sh            (run from promo/ after render + soundtrack)
set -euo pipefail
cd "$(dirname "$0")/.."

OUT=out
REL=release
mkdir -p "$REL"

ls "$OUT"/chunks/c*.mp4 | sort | sed "s|^$OUT/chunks/|file '|; s|$|'|" > "$OUT/chunks/list.txt"
ffmpeg -y -loglevel error -f concat -safe 0 -i "$OUT/chunks/list.txt" -c copy "$OUT/video_only.mp4"

# Final encode: H.264 1080p30 + AAC music & effects mix, Arabic captions burned in
# (and also carried as a selectable subtitle track).
ffmpeg -y -loglevel error -i "$OUT/video_only.mp4" -i "$OUT/mix.wav" -i "$OUT/captions.srt" \
  -map 0:v -map 1:a -map 2:s \
  -c:v libx264 -preset slow -crf "${CRF:-21}" -pix_fmt yuv420p -movflags +faststart \
  -c:a aac -b:a 256k -c:s mov_text \
  -metadata:s:a:0 title="Music & FX (voice-over ready)" -metadata:s:s:0 language=ara \
  -shortest "$REL/BR_promo_1080p.mp4"

cp "$OUT/mix.wav" "$REL/BR_music_fx_mix.wav"
cp "$OUT/music.wav" "$REL/BR_music_stem.wav"
cp "$OUT/sfx.wav" "$REL/BR_sfx_stem.wav"
cp "$OUT/captions.srt" "$REL/BR_captions_ar.srt"
cp "$OUT/vo_cue_sheet.txt" "$REL/BR_vo_cue_sheet.txt"
ls -la "$REL"
