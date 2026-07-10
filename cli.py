#!/usr/bin/env python3
"""InkMemories — CLI 入口"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="InkMemories — AI 照片回忆系统")
    sub = parser.add_subparsers(dest="command")

    # analyze
    p_analyze = sub.add_parser("analyze", help="分析新照片")
    p_analyze.add_argument("-j", "--concurrency", type=int, default=None, help="并发数")
    p_analyze.add_argument("-n", "--limit", type=int, default=None, help="最多分析几张")

    # server
    p_server = sub.add_parser("server", help="启动 WebUI 服务器")

    # daily
    p_daily = sub.add_parser("daily", help="显示今日精选")

    args = parser.parse_args()

    if args.command == "analyze":
        import config
        if args.concurrency:
            config.CONCURRENCY = args.concurrency
        if args.limit:
            config.BATCH_LIMIT = args.limit
        from analyzer import run_analysis
        run_analysis()

    elif args.command == "server":
        import config
        import database
        database.init_db()
        from server import app
        logger.info(f"启动 WebUI: http://0.0.0.0:{config.FLASK_PORT}")
        app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=False)

    elif args.command == "daily":
        from daily import get_daily_summary
        summary = get_daily_summary()
        print(f"\n📅 {summary['date']} · {summary['weekday']}")
        print(f"   数据库共 {summary['total_in_db']} 张照片\n")
        if summary["photos"]:
            for i, p in enumerate(summary["photos"], 1):
                dc = p.get("daily_caption") or ""
                dsc = p.get("daily_side_caption") or ""
                print(f"  {i}. [{p['type']}] 回忆:{p['memory_score']:.0f} 美观:{p['beauty_score']:.0f}")
                if dc:
                    print(f"     {dc[:80]}")
                if dsc:
                    print(f"     「{dsc}」")
                print()
        else:
            print("  暂无精选，请先运行 analyze 命令。")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
