"""Phase 1 snapshot replay against a real Heptabase whiteboard.

Per Codex P1 review 2026-04-27: this is a SNAPSHOT REPLAY, not a live
MCP integration test. The hardcoded `_SMOKE_WHITEBOARD` was captured
once via `mcp__heptabase-mcp__get_whiteboard_with_objects` on
2026-04-27 and pasted in. It exercises the modules end-to-end with
real-shape Chinese content (validating spec §3.7 CJK acceptance),
but it does NOT validate the live HeptabaseMCPClient wiring path —
that path is intentionally NotImplementedError in Phase 1.

When Phase 2+ wires the live MCP, replace this script's
`_InMemoryClient` with a thin wrapper around the live MCP tools.

Usage: python -m scripts.propose_links.smoke_run
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from scripts.propose_links.inventory import build_inventory
from scripts.propose_links.maturity_detect import detect_maturity
from scripts.propose_links.output import dryrun_filename, render_dryrun_markdown
from scripts.propose_links.tfidf_prefilter import (
    assert_cjk_gate,
    build_tfidf_prefilter,
)


# Snapshot of cutemo0953's Heptabase whiteboard "iRehab Service"
# captured 2026-04-27 via mcp__heptabase-mcp__get_whiteboard_with_objects
# Content fields are first-chunk excerpts (≤500 chars per spec §2.3).
_SMOKE_WHITEBOARD: dict[str, Any] = {
    "id": "5540d525-008d-432c-8069-b29f4cac779c",
    "name": "iRehab Service",
    "objects": [
        {
            "id": "0418ab33", "type": "card",
            "title": "Lemon v0.0.7",
            "tags": [],
            "content": "我換瀏覽器後便可以成功回報疼痛指數，我猜測是否是coockies的問題？回報疼痛指數的頁面在更新後仍然無法填入新的資料。身分證字號與電話號碼在表格仍然希望完整填入spreadsheet，少去第一個字碼是指「只需核對後9碼」。圖片仍未正常顯示。除了給google drive連結以外，有沒有其他方式？",
        },
        {
            "id": "0f7520eb", "type": "card",
            "title": "额外的建议",
            "tags": [],
            "content": "确保敏感数据的安全。虽然设置为「任何人」可以解决访问问题，但要注意数据的安全性。请确保在代码中做好权限控制，例如在处理用户提交的数据时，验证身份信息。日志记录和错误处理：在代码中添加日志记录，方便排查问题。",
        },
        {
            "id": "1b639ddf", "type": "card",
            "title": "我決定要重新佈署一次。請根據上面所討論過的內容，給我一份更新的程式碼，從code.gs開始renew",
            "tags": [],
            "content": "好的，為了協助您重新部署應用程式，我將根據之前討論的內容，提供更新的程式碼，從 Code.gs 開始，並包括所有相關的 HTML 檔案。設定您的試算表 ID 與圖片存放的資料夾 ID。前端頁面渲染、病患註冊、提交疼痛指數、檢查重複、上傳圖片到 Google Drive。",
        },
        {
            "id": "1ffd7cce", "type": "card",
            "title": "Lemon v0.0.4",
            "tags": [],
            "content": "用doGet函數，讓Registration.html 和 PainReport.html共享同一個後台資料，疼痛指數回報頁面就能正確地訪問到註冊資訊。PainReports的欄位跑掉。註冊處理函數請確保列索引正確。提交疼痛指數函數請確保列索引正確。",
        },
        {
            "id": "24a2d4eb", "type": "card",
            "title": "WebApp links",
            "tags": [],
            "content": "9/17/2024 我這兩天用chatGPT 01-preview做了網頁版的WebApp, 大抵上把之前做的基本功能做出來了：註冊、疼痛指數、上傳圖片、後台spreadsheet、上傳圖片的資料夾。",
        },
        {
            "id": "2845dcb9", "type": "card",
            "title": "Lemon v0.0.3",
            "tags": [],
            "content": "身分證字號 ＋ 手機號碼登入。允許瀏覽器記住該使用者資訊，但會顯示如xxxxx06這樣的資訊內容。響應式頁面。+iRehab logo。Code.gs 設定您的試算表 ID。前端頁面渲染、病患註冊處理、提交疼痛指數、獲取病患歷史數據。",
        },
        {
            "id": "2b26d197", "type": "card",
            "title": "Lemon v0.2.1",
            "tags": [],
            "content": "隐私和安全考虑：数据保护，确保所有患者数据的存储和传输符合相关的隐私法规，如 GDPR、HIPAA 等。访问控制：在应用程序中，验证用户身份，确保只有患者本人或授权的医疗人员可以查看数据。数据加密：考虑对敏感数据进行加密存储。",
        },
        {
            "id": "2f1deba1", "type": "card",
            "title": "Lemon v0.0.2",
            "tags": [],
            "content": "+Registration page +VAS history display。Code.gs 請將此程式碼貼到您的 Apps Script 編輯器中的 Code.gs 檔案中。前端頁面渲染、病患註冊處理、提交疼痛指數、獲取病患歷史數據。",
        },
        {
            "id": "5c8adac7", "type": "card",
            "title": "Lemon v0.2",
            "tags": [],
            "content": "我覺得每日回報疼痛指數與傷口照片後，如果系統可以自己做出一份「歷程報告」、或「儀表板dashboard」就太好了。未來可以納入更多生理資訊進來，更接近於dashboard in realtime。資料收集與存儲：已經通過 Google Apps Script 將疼痛指數和伤口照片的數據收集並存儲到 Google Sheets 和 Google Drive 中。",
        },
        {
            "id": "787e1c25", "type": "card",
            "title": "Lemon v0.0.1",
            "tags": [],
            "content": "from Claude.ai。VAS score only。Adjusted UI。code.gs 請將此代碼粘貼到您的 Apps Script 編輯器中的 Code.gs 文件中。設定您的電子表格 ID。渲染前端頁面、處理表單提交。",
        },
        {
            "id": "9b82188f", "type": "card",
            "title": "Lemon v0.0.5",
            "tags": [],
            "content": "開一個新的試算表。註冊頁面有正常顯示之前我希望看到的UI。疼痛指數的頁面只有顯現標題「歡迎使用疼痛指數管理系統」，其餘欄位並未正常顯示。表單sheet 也沒有疼痛指數回報。",
        },
        {
            "id": "b1beb920", "type": "card",
            "title": "Links",
            "tags": [],
            "content": "https://script.google.com/a/macros/denovortho.com/s/AKfycbyUS-4tZ7kqYqg3z2ZWCmYPpYF3F-apDgFxyYqTRZ6qNHH1siZzus9iUU6SOe_GpxKH/exec?page=report",
        },
        {
            "id": "c1a5f5e8", "type": "card",
            "title": "Lemon v0.1.0",
            "tags": [],
            "content": "如果我想做一個圖片上傳器（webapp形式），讓病人上傳術後每日傷口照片，照片自動傳到公司的Google Drive，後台前台應該怎麼建構？前端：一個網頁表單，讓病人可以選擇並上傳照片。後端：Google Apps Script 代碼，用於處理上傳的圖片，將其保存到指定的 Google Drive 資料夾。",
        },
        {
            "id": "daf41a3e", "type": "card",
            "title": "Lemon v0.0.6",
            "tags": [],
            "content": "手機號碼我在註冊頁面填入的是 0953083190, spreadsheet表單顯示的是953083190，少了開頭的0。我猜疼痛指數頁面所填的手機號碼與身分證字號必須完全一致。可以改成身分證字號後9碼、電話號碼後9碼正確即可？疼痛回報頁面一旦填入就無法修改。",
        },
        {
            "id": "ddd20e13", "type": "card",
            "title": "Lemon v0.2 -存取權錯誤",
            "tags": [],
            "content": "上傳圖片的網頁會顯示「要求存取權」頁面，但是後台並未收到任何訊息。請問是哪個部分的權限需要開啟嗎？應用程式的部署權限設置不正確、執行身份不正確、Google Drive 資料夾的權限設置、修改代碼後未重新部署。",
        },
        {
            "id": "e7afb6b2", "type": "card",
            "title": "Lemon v0.0.8",
            "tags": [],
            "content": "目前已解決以上問題。疼痛指數回報後，資料會正常匯入表格，新資訊也會覆蓋舊資訊。但是新資訊的填寫時間仍會顯示第一筆資訊的填寫時間。希望表格內的時間也會被覆寫，但被覆寫的舊時間與舊疼痛指數可以被移到新表格被記錄。彈出視窗仍未關閉。字型可以改用Ariel嗎？",
        },
        {
            "id": "ee916a75", "type": "card",
            "title": "Lemon v0.1.1",
            "tags": [],
            "content": "上傳圖片失敗：上傳失敗：Blob object must have non-null name for this operation。上傳圖片網頁的logo未正常顯示。返回疼痛指數頁面：按鈕無法回到疼痛指數頁面。當我們使用 folder.createFile(blob) 方法創建文件時，blob 對象必須具有非空的名稱。",
        },
        {
            "id": "f83a5a6d", "type": "card",
            "title": "愛復健部落格",
            "tags": [],
            "content": "目前部落格的資料看起來都還是存在資料庫裡面。",
        },
        # Three sections — should be skipped by inventory ANALYZABLE_TYPES filter
        {"id": "section-1", "type": "section", "title": "權限問題"},
        {"id": "section-2", "type": "section", "title": "註冊＋疼痛"},
        {"id": "section-3", "type": "section", "title": "上傳圖片"},
    ],
    "connections": [
        {"from": "787e1c25", "to": "2f1deba1"},
        {"from": "1ffd7cce", "to": "9b82188f"},
        {"from": "2f1deba1", "to": "2845dcb9"},
        {"from": "c1a5f5e8", "to": "ee916a75"},
        {"from": "5c8adac7", "to": "ddd20e13"},
        {"from": "0418ab33", "to": "e7afb6b2"},
        {"from": "9b82188f", "to": "daf41a3e"},
        {"from": "2845dcb9", "to": "1ffd7cce"},
        {"from": "daf41a3e", "to": "0418ab33"},
        {"from": "ddd20e13", "to": "2b26d197"},
    ],
}


class _InMemoryClient:
    def __init__(self, wb):
        self._wb = wb

    def search_whiteboards(self, _kw):
        return [{"id": self._wb["id"], "name": self._wb["name"]}]

    def get_whiteboard_with_objects(self, _id):
        return self._wb

    def get_object(self, oid):
        for o in self._wb["objects"]:
            if o["id"] == oid:
                return o
        raise LookupError(oid)


def main(argv: list[str] | None = None) -> int:
    out_dir = Path("propose_links")
    client = _InMemoryClient(_SMOKE_WHITEBOARD)

    inventory = build_inventory(_SMOKE_WHITEBOARD["id"], client)
    print(
        f"[smoke] inventory: {inventory['card_count']} analyzable cards, "
        f"scale_tier={inventory['scale_tier']}, "
        f"skipped={inventory['skipped']}, "
        f"existing_connections={len(inventory['existing_connections'])}",
        file=sys.stderr,
    )

    maturity = detect_maturity(inventory, registry_path=None)
    print(f"[smoke] maturity: {maturity}", file=sys.stderr)

    pair_scores, diagnostics = build_tfidf_prefilter(inventory["cards"])
    print(
        f"[smoke] pairs: {diagnostics['pair_count_total']} total, "
        f"{diagnostics['pair_count_returned']} returned, "
        f"top10 spread={diagnostics['top10_score_spread']}",
        file=sys.stderr,
    )

    try:
        assert_cjk_gate(diagnostics)
        print("[smoke] CJK gate: PASS", file=sys.stderr)
    except RuntimeError as e:
        print(f"[smoke] CJK gate: FAIL — {e}", file=sys.stderr)
        return 1

    md = render_dryrun_markdown(inventory, maturity, pair_scores, diagnostics)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / dryrun_filename(
        inventory["whiteboard_name"], output_dir=out_dir
    )
    out_path.write_text(md, encoding="utf-8")
    print(f"[smoke] dry-run written to {out_path}", file=sys.stderr)

    # Sanity-print top 3 pairs for human eyeballing
    print("\n[smoke] Top 3 pairs:", file=sys.stderr)
    for rank, (i, j, score) in enumerate(pair_scores[:3], 1):
        a = inventory["cards"][i]
        b = inventory["cards"][j]
        print(f"  {rank}. {score:.4f}  {a['title'][:30]} ↔ {b['title'][:30]}", file=sys.stderr)

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
