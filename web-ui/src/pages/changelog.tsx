import { Timeline, Typography } from "antd";

const { Title, Paragraph, Text } = Typography;

type LogEntry = {
  date: string;
  added: string[];
  fixed: string[];
};

/** 按时间倒序：最新的在上面 */
const CHANGELOG: LogEntry[] = [
  {
    date: "2026-05-07",
    added: [
      "首页「分析单只股票」：弹窗输入代码，调用 POST /api/analyze 并刷新列表",
      "导航「更新日志」模块，集中记录功能迭代与修复",
      "「新闻数量」列点击弹窗，接入 GET /api/news/{stock_code} 展示新闻明细",
      "POST /api/analyze 支持可选参数 stock_code，单股抓取与分析不影响原「新增股」流程",
    ],
    fixed: ["复制股票名称在非 Chrome 下失败：增加 execCommand 降级方案"],
  },
];

export default function ChangelogPage() {
  return (
    <div>
      <Title level={2}>更新日志</Title>
      <Paragraph type="secondary">
        记录各版本新增能力与问题修复，便于对照环境与排查。
      </Paragraph>

      <Timeline
        items={CHANGELOG.map((entry) => ({
          color: "blue",
          children: (
            <div style={{ paddingBottom: 16 }}>
              <Text strong style={{ fontSize: 16 }}>
                {entry.date}
              </Text>

              {entry.added.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <Text type="success">新增</Text>
                  <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
                    {entry.added.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </div>
              )}

              {entry.fixed.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <Text type="warning">修复</Text>
                  <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
                    {entry.fixed.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ),
        }))}
      />
    </div>
  );
}
