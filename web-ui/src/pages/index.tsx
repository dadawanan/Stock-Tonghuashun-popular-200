import { Button, message, Table } from "antd";
import { useEffect, useState } from "react";
import { analysisApi, AnalysisResult } from "../utils";
export default function HomePage() {
  const [data, setData] = useState<AnalysisResult[]>([]);
  const [running, setRunning] = useState(false);

  const columns = [
    {
      title: "股票代码",
      dataIndex: "stock_code",
      key: "stock_code",
    },
    {
      title: "股票名称",
      dataIndex: "stock_name",
      key: "stock_name",
      render: (text: string) => (
        <a
          onClick={
            // 复制
            () => {
              navigator.clipboard
                .writeText("text")
                .then(() => {
                  console.log("复制成功！");
                })
                .catch((err) => {
                  console.error("复制失败：", err);
                });
            }
          }
        >
          {text}
        </a>
      ),
    },
    {
      title: "Address",
      dataIndex: "address",
      key: "address",
    },
  ];

  const getStocks = () => {
    analysisApi.getList().then((res) => {
      setData(res);
    });
  };

  useEffect(() => {
    getStocks();
  }, []);

  return (
    <div>
      <Button
        type="primary"
        disabled={running}
        onClick={() => {
          setRunning(true);
          message.success("开始获取新增人气股票");
          analysisApi.runAll().then((res) => {
            message.success(
              `获取完成,成功获取到${res.analysis.result_count}条数据`,
            );
            getStocks();
            setRunning(false);
          });
        }}
      >
        获取新增人气股票
      </Button>
      <Table dataSource={data} columns={columns}></Table>
    </div>
  );
}
