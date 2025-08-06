# Flask debugger demo 后端

演示 Flask debugger demo 效果

# 启动命令

mongo 数据库连接在 config.properties 需自行配置，否则不能正常访问接口

```bash
./deployment/local/build_image.sh # 构建镜像
./deployment/local/start.sh # 启动后端，访问 localhost:3004
./deployment/local/start.sh -b # 进入后端容器
./deployment/local/start.sh -p # 本地模仿生产环境
```

# 调试相关

以下调试步骤需要在 `./deployment/local/start.sh` 启动后才能跑通

1. 断点调试：打开 vscode 运行和调试面板，切换到 Debug Flask (Docker)，点击启动成功后，给某个接口打上断点，访问接口即可开始断点调试
2. flask-debug-toolbar
   1. 首页：访问 http://localhost:3004/ 首页，可以看到 flask debug toolbar 页面
   2. History 面板：用 postman 或前端页面 replay 接口，请求的接口需要带上 ?\_debug 参数，此时 History 面板才会出现请求数据，可以看到对应的请求历史以及关联的数据库访问语句
   3. MongoDb 面板：所有 mongo 数据库的访问记录，包含请求和非请求部分（比如定时任务触发的）
   4. 举例：当然也支持直接访问接口 `http://localhost:3004/api/path1/path2/path3/test?id=1&_debug`, 此时可以直接查看接口历史和所有数据库访问语句
3. flask_profiler: 访问 http://localhost:3004/flask-profiler
