from app import app

# 确保 app 实例在 Vercel 环境中正确运行
# Vercel 会直接导入这个模块，而不是执行 __main__ 块
application = app

if __name__ == "__main__":
    app.run()