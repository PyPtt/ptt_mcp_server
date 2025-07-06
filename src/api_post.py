

from typing import Dict, Any, Optional, List, Tuple

import PyPtt
from fastmcp import FastMCP

from utils import _call_ptt_service, _handle_ptt_exception

def register_tools(mcp: FastMCP, memory_storage: Dict[str, Any], version: str):
    @mcp.tool()
    def get_post_index_range() -> Dict[str, Any]:

        """
        取得 PTT 文章的索引範圍。

        :return: Dict[str, Any]: 一個包含 prompt 的字典，prompts 欄位將會教導你如何完成目標。

        """

        prompt = """這個函式的目標是使用 PTT MCP server 的功能，找到在指定看板（board）和指定日期（target_date）下，所有文章的起始索引（start_index）和結束索引（end_index）。

可用工具函式：

get_newest_index(board: str) -> int：取得看板最新的文章索引。

get_post(board: str, index: int) -> str：取得指定索引文章的日期字串（格式為 "M/DD"，例如 "7/6"）。如果文章不存在或無法取得日期，可能會失敗或回傳空值。你可以使用查詢模式更有效率。

執行計畫
第 1 步：初始化

設定目標： 假設我們要找 board = "Gossiping" 在 target_date = "7/6" 的文章。

取得搜尋上界： 呼叫 get_newest_index(board="Gossiping") 取得最大索引，稱之為 max_index。

設定搜尋範圍： low = 1, high = max_index。

第 2 步：尋找 start_index (當天的第一篇文章)

目標： 找到第一個日期為 "7/6" 的索引。

方法： 使用二元搜尋法。在迴圈中，你比較 get_post(board="Gossiping", index=mid) 的日期和 target_date。

如果 mid 的日期 早於 "7/6" (例如 "7/5")，表示 start_index 肯定在更右邊。所以更新 low = mid + 1。

如果 mid 的日期 等於或晚於 "7/6" (例如 "7/6" 或 "7/7")，表示 start_index 可能就是 mid，或者在更左邊。所以我們先把 mid 當作可能的答案 (ans = mid)，然後繼續往左邊找看看有沒有更早的，更新 high = mid - 1。

範例流程：

get_post(board="Gossiping", index=100) -> "7/5" => 太早了，往右找 (low 變大)

get_post(board="Gossiping", index=200) -> "7/7" => 太晚了，200 可能是答案，但要往左找 (ans = 200, high = 199)

get_post(board="Gossiping", index=150) -> "7/6" => 150 可能是答案，但要繼續往左找 (ans = 150, high = 149)

結果： 整個迴圈結束後，ans 變數的值就是我們要的 start_index。

第 3 步：尋找 end_index (當天的最後一篇文章)

目標： 找到最後一個日期為 "7/6" 的索引。

方法： 再次使用二元搜尋法（low 和 high 需要重設為 1 和 max_index）。

如果 mid 的日期 晚於 "7/6" (例如 "7/7")，表示 end_index 肯定在更左邊。所以更新 high = mid - 1。

如果 mid 的日期 等於或早於 "7/6" (例如 "7/6" 或 "7/5")，表示 end_index 可能就是 mid，或者在更右邊。所以我們先把 mid 當作可能的答案 (ans = mid)，然後繼續往右邊找看看有沒有更晚的，更新 low = mid + 1。

範例流程：

get_post(board="Gossiping", index=300) -> "7/7" => 太晚了，往左找 (high 變小)

get_post(board="Gossiping", index=250) -> "7/6" => 250 可能是答案，但要繼續往右找 (ans = 250, low = 251)

結果： 整個迴圈結束後，ans 變數的值就是我們要的 end_index。

第 4 步：驗證並回報

在找到 start_index 和 end_index 後，你必須做最後的驗證。呼叫 get_post(board="Gossiping", index=start_index) 和 get_post(board="Gossiping", index=end_index) 確認它們的日期都是 target_date ("7/6")。

如果驗證成功，且 start_index <= end_index，則回報：「在 Gossiping 板，日期 7/6 的文章索引範圍是從 start_index 到 end_index。」

如果找不到，或驗證失敗（例如，找到的 start_index 日期是 "7/7"，代表當天根本沒文章），則回報：「在 Gossiping 板找不到日期 7/6 的任何文章。」"""

        return {
            "success": False,
            "message": f"請遵循 prompt",
            "code": "FOLLOW_PROMPTS",
            "prompts": prompt
        }