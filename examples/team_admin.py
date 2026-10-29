#!/usr/bin/env python3
"""自托管团队管理：创建成员、分组、模型、镜像等（管理员）。

需要团队会话（先 team_login）。示例默认只做只读操作，
写操作以注释形式给出，避免误操作。

用法：
    export MONKEYCODE_EMAIL=you@example.com
    export MONKEYCODE_PASSWORD=your_password
    export MONKEYCODE_TEAM_EMAIL=admin@example.com
    export MONKEYCODE_TEAM_PASSWORD=admin_password
    python examples/team_admin.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monkeycode import MonkeyCodeClient


def main() -> None:
    client = MonkeyCodeClient(
        email=os.environ.get("MONKEYCODE_EMAIL", ""),
        password=os.environ.get("MONKEYCODE_PASSWORD", ""),
    )
    with client:
        # 团队登录（管理员）
        client.team_login(
            email=os.environ.get("MONKEYCODE_TEAM_EMAIL", ""),
            password=os.environ.get("MONKEYCODE_TEAM_PASSWORD", ""),
        )

        # 只读：团队概览
        print("团队用户：", client.team_list_users())
        print("团队分组：", client.team_list_groups())
        print("团队模型：", client.team_list_models())
        print("团队镜像：", client.team_list_images())
        print("团队技能：", client.team_list_skills())

        # 写操作示例（默认注释，取消注释并填写参数后执行）
        # user = client.team_add_user_with_password(email="member@example.com", username="member")
        # print("新成员初始密码：", user)
        # client.team_update_group(group_id, "新分组名")
        # client.team_create_model(name="我的模型", provider="openai", **{})
        # client.team_create_image(image_name="ubuntu", is_default=True)


if __name__ == "__main__":
    main()