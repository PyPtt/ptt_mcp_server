from datetime import datetime
from typing import Dict, Any

import PyPtt
from fastmcp import FastMCP

from utils import _call_ptt_service


def register_tools(mcp: FastMCP, memory_storage: Dict[str, Any], version: str):
    @mcp.tool()
    def get_board_rules() -> Dict[str, Any]:
        """
        取得 PTT 看板規則。

        註記：此函式必須先登入 PTT。

        Returns:
            Dict[str, Any]: 包含操作結果的字典。
                            成功時: {'success': True, 'message': str, 'data': List[str]}
                            失敗時: {'success': False, 'message': str, 'code': str, 'prompt': str}
        """

        prompt = """
        請使用 get_bottom_post_list 來取得置底文章，因為板規通常都會置底。
        
        如果找不到版規，請使用 get_newest_index(index_type="BOARD", board=board, search_list=[("KEYWORD", "版規")]) 來取得有版規在標題中的文章列表。
        
        註記：版規可能叫做「版規」or 「板規」。
        """

        return {
            'success': False,
            'message': '請遵循提示。',
            'code': 'FOLLOW_PROMPT',
            'prompt': prompt
        }

    @mcp.tool()
    def get_post_index_range(board: str, target_date: str) -> Dict[str, Any]:
        """
        取得 PTT 文章在指定看板和日期下的索引範圍。

        註記：此函式必須先登入 PTT。

        Args:
            board (str): 看板名稱，例如 "Gossiping"。
            target_date (str): 目標日期字串，格式為 "YYYY/MM/DD"，例如 "1987/09/06"。

        Returns:
            Dict[str, Any]: 包含操作結果的字典。
                            成功時: {'success': True, 'start_index': int, 'end_index': int}
                            失敗時: {'success': False, 'message': str}
        """

        # Helper to parse and compare dates
        def parse_date_str(date_str: str) -> datetime:
            # Add a dummy year to make it a full date for comparison.
            # Assuming all dates are within the current year for simplicity.
            # For cross-year comparisons, more complex logic would be needed.

            if date_str.count('/') == 2:
                return datetime.strptime(date_str, "%Y/%m/%d")

            current_year = datetime.now().year
            return datetime.strptime(f"{current_year}/{date_str}", "%Y/%m/%d")

        try:
            target_date = parse_date_str(target_date)
        except ValueError:
            return {"success": False,
                    "message": f"Invalid target_date_str format: {target_date}. Expected 'YYYY/MM/DD'."}

        # 1. Get the newest index for the board
        newest_index_response = _call_ptt_service(
            memory_storage,
            "get_newest_index",
            index_type=PyPtt.NewIndex.BOARD,
            board=board,
        )
        if not newest_index_response.get('success'):
            return {"success": False,
                    "message": f"Failed to get newest index for board {board}: {newest_index_response.get('message')}"}
        max_index = newest_index_response.get('data')

        if max_index is None or max_index < 1:
            return {"success": False, "message": f"No posts found for board {board}."}

        # Binary search for start_index
        start_index = -1
        low, high = 1, max_index
        while low <= high:
            mid = (low + high) // 2
            post_response = _call_ptt_service(
                memory_storage,
                "get_post",
                board=board,
                index=mid,
                query=True,
            )

            if not post_response.get('success') or not post_response.get('data') or not post_response['data'].get(
                    'list_date'):
                # If post not found or date missing, try to narrow down the search
                # This might happen for deleted posts or invalid indices.
                # For simplicity, we'll assume it's an invalid index and try higher.
                low = mid + 1
                continue

            post_date_str = post_response['data']['list_date']
            try:
                post_date = parse_date_str(post_date_str)
            except ValueError:
                # If post date is malformed, skip and try higher
                low = mid + 1
                continue

            if post_date < target_date:
                low = mid + 1
            elif post_date == target_date:
                start_index = mid
                high = mid - 1  # Try to find an earlier one
            else:  # post_date > target_date
                high = mid - 1

        # Binary search for end_index
        end_index = -1
        low, high = 1, max_index  # Reset search range
        while low <= high:
            mid = (low + high) // 2
            post_response = _call_ptt_service(
                memory_storage,
                "get_post",
                board=board,
                index=mid,
                query=True,
            )

            if not post_response.get('success') or not post_response.get('data') or not post_response['data'].get(
                    'list_date'):
                low = mid + 1
                continue

            post_date_str = post_response['data']['list_date']
            try:
                post_date = parse_date_str(post_date_str)
            except ValueError:
                low = mid + 1
                continue

            if post_date > target_date:
                high = mid - 1
            elif post_date == target_date:
                end_index = mid
                low = mid + 1  # Try to find a later one
            else:  # post_date < target_date
                low = mid + 1

        if start_index == -1 or end_index == -1 or start_index > end_index:
            return {"success": False, "message": f"在 {board} 板找不到日期 {target_date} 的任何文章。"}
        else:
            # Final verification (as suggested in the prompt)
            # Verify start_index
            start_post_response = _call_ptt_service(
                memory_storage,
                "get_post",
                board=board,
                index=start_index,
                query=True,
            )
            if not start_post_response.get('success') or not start_post_response.get('data') or parse_date_str(
                    start_post_response['data'].get('list_date', '')) != target_date:
                return {"success": False,
                        "message": f"在 {board} 板找不到日期 {target_date} 的任何文章 (start_index verification failed)."}

            # Verify end_index
            end_post_response = _call_ptt_service(
                memory_storage,
                "get_post",
                board=board,
                index=end_index,
                query=True,
            )
            if not end_post_response.get('success') or not end_post_response.get('data') or parse_date_str(
                    end_post_response['data'].get('list_date', '')) != target_date:
                return {"success": False,
                        "message": f"在 {board} 板找不到日期 {target_date} 的任何文章 (end_index verification failed)."}

            return {"success": True, "start_index": start_index, "end_index": end_index}
