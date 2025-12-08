classdef Class_example
    %CLASS_EXAMPLE 此处显示有关此类的摘要
    %   此处显示详细说明

    properties
        result
    end

    methods
        function obj = Class_example()
            %CLASS_EXAMPLE 构造此类的实例
            %   此处显示详细说明

        end

        function obj = add(obj,a,b)
            % 加法方法
            obj.result = a + b;
        end
        function obj = subtract(obj,a,b)
            % 减法方法
            obj.result = a - b;
        end
    end
end

