本地检索索引

tactical_foundation_chunks.json 是由 knowledge_base/ingestion/foundation_ingestion.py 从 seed/tactical_foundations.json 生成的派生文件。

维护知识时先修改 seed 中的原始条目，再运行：

    D:\python\python.exe scripts\build_tactical_foundation_index.py

不要直接编辑索引文件，否则下次构建会覆盖改动。
