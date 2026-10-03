import json
import os

def determine_question_type(item):
    """
    根据题目特征智能判断题型：
    1. 简答题：包含 'answer' 字段
    2. 判断题：包含 'new-answer' 且内容为 '正确' 或 '错误'
    3. 选择/填空题：包含 'new-answer' 但不是判断题
    """
    if 'answer' in item:
        return "简答题", item['answer']
    
    if 'new-answer' in item:
        ans = str(item['new-answer']).strip()
        if ans in ['正确', '错误']:
            return "判断题", ans
        else:
            return "选择/填空题", ans
            
    return "未知题型", "（未找到对应答案字段）"

def search_questions():
    file_path = 'test.json'

    if not os.path.exists(file_path):
        print(f"\n❌ 错误：找不到 {file_path}")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"\n❌ 解析 JSON 出错: {e}")
        return

    # 漂亮的欢迎界面
    print("\n" + "═" * 60)
    print(" 🌟 电力安全工规（信息部分）智能搜索工具 🌟 ".center(52))
    print("═" * 60)

    while True:
        keyword = input("\n🔍 请输入搜索关键字: ").strip()

        if keyword.lower() in ['exit', 'quit', '退出']:
            print("👋 程序已退出，祝你逢考必过！")
            break
        if not keyword:
            continue

        # 匹配逻辑
        results = [item for item in data if keyword in item.get('question', '')]

        if results:
            print(f"\n✅ 为您找到 {len(results)} 条包含 “{keyword}” 的题目：\n")
            
            # 遍历并使用卡片式打印
            for idx, res in enumerate(results, 1):
                question = res.get('question', '无题目内容')
                q_type, answer = determine_question_type(res)

                # 根据不同题型匹配不同的 Emoji 图标
                type_icon = "📝"
                if q_type == "判断题":
                    type_icon = "⚖️ "
                elif q_type == "简答题":
                    type_icon = "💬"
                elif q_type == "选择/填空题":
                    type_icon = "🔠"

                # 卡片式排版输出
                print(f"╭─── 【第 {idx:02d} 题】 {type_icon} [{q_type}] ─────────────")
                print(f"│ ❓ 问题：{question}")
                print(f"│ 💡 答案：{answer}")
                print(f"╰───────────────────────────────────────────────────\n")
        else:
            print(f"❌ 未找到包含 “{keyword}” 的内容，请尝试精简或更换关键词。")

if __name__ == "__main__":
    search_questions()