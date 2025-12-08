% build_main_func_python.m
% 1) 主函数文件 列出所有“入口”函数文件（每一个都要在 Python 中被调用）
entryPoints = [
    "add_func.m"
    "sub_func.m"
    % "Class_example.m" % TODO: Matlab2024b暂时不支持类的打包
    % "mul_func.m"
    % 如果还有别的入口函数，就在这里继续加
    % "other_func.m"
    ];

% 2) 输出目录（建议用绝对路径）
outputDir = ".\example_python312_matlab2024b";  % 自己改成实际路径,可随意自定义，但是建议写清楚所用的python版本和matlab版本

% 3) 创建打包选项（包含依赖的 .mat）
opts = compiler.build.PythonPackageOptions(entryPoints, ...
    PackageName          = "ExamplePkg", ...   % Python 包名,自己改成自己想要的包名
    OutputDir            = outputDir, ...% 输出目录
    AdditionalFiles      = [], ...      % 需要一起打包的数据如：["test.mat", "test02.mat"], ... % 需要一起打包的数据
    AutoDetectDataFiles  = "on", ...    % 自动检测数据文件
    Verbose              = "on" ...     % 打包时显示详细信息
    );

% 4) 真正构建 Python 包
buildResults = compiler.build.pythonPackage(opts);
