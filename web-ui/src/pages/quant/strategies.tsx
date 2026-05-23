import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Col,
  Form,
  Input,
  message,
  Modal,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { quantApi, Strategy } from "../../utils";

const { Title } = Typography;

const strategyTypeLabels: Record<string, { label: string; color: string }> = {
  popularity: { label: "人气榜策略", color: "blue" },
  sentiment: { label: "情绪驱动策略", color: "green" },
  technical: { label: "技术面策略", color: "orange" },
  multi_factor: { label: "多因子策略", color: "purple" },
};

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form] = Form.useForm();

  const loadStrategies = async () => {
    setLoading(true);
    try {
      const data = await quantApi.listStrategies();
      setStrategies(Array.isArray(data) ? data : []);
    } catch {
      message.error("加载策略列表失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStrategies();
  }, []);

  const handleCreate = () => {
    setEditingId(null);
    form.resetFields();
    setModalOpen(true);
  };

  const handleEdit = (record: Strategy) => {
    setEditingId(record.id);
    form.setFieldsValue({
      name: record.name,
      type: record.type,
      description: record.description,
      params: JSON.stringify(record.params, null, 2),
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const params = values.params ? JSON.parse(values.params) : {};

      if (editingId) {
        await quantApi.updateStrategy(editingId, {
          name: values.name,
          params,
          description: values.description,
        });
        message.success("策略已更新");
      } else {
        await quantApi.createStrategy({
          name: values.name,
          type: values.type,
          params,
          description: values.description,
        });
        message.success("策略已创建");
      }

      setModalOpen(false);
      loadStrategies();
    } catch (e: any) {
      if (e?.message) {
        message.error(e.message);
      }
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await quantApi.deleteStrategy(id);
      message.success("策略已删除");
      loadStrategies();
    } catch {
      message.error("删除失败");
    }
  };

  const columns: ColumnsType<Strategy> = [
    { title: "ID", dataIndex: "id", width: 60 },
    { title: "名称", dataIndex: "name", width: 150 },
    {
      title: "类型",
      dataIndex: "type",
      width: 130,
      render: (type: string) => {
        const meta = strategyTypeLabels[type] || { label: type, color: "default" };
        return <Tag color={meta.color}>{meta.label}</Tag>;
      },
    },
    {
      title: "参数",
      dataIndex: "params",
      ellipsis: true,
      render: (params: Record<string, any>) => (
        <span style={{ fontSize: 12, color: "#666" }}>
          {JSON.stringify(params).slice(0, 80)}...
        </span>
      ),
    },
    { title: "描述", dataIndex: "description", ellipsis: true },
    {
      title: "状态",
      dataIndex: "is_active",
      width: 80,
      render: (active: boolean) => (
        <Tag color={active ? "success" : "default"}>
          {active ? "启用" : "禁用"}
        </Tag>
      ),
    },
    {
      title: "操作",
      width: 150,
      render: (_, record) => (
        <Space>
          <Button size="small" onClick={() => handleEdit(record)}>
            编辑
          </Button>
          <Button size="small" danger onClick={() => handleDelete(record.id)}>
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Title level={3}>策略管理</Title>
        <Button type="primary" onClick={handleCreate}>
          新建策略
        </Button>
      </div>

      <Card>
        <Table
          columns={columns}
          dataSource={strategies}
          rowKey="id"
          loading={loading}
          pagination={false}
        />
      </Card>

      <Modal
        title={editingId ? "编辑策略" : "新建策略"}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="策略名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="type" label="策略类型" rules={[{ required: true }]}>
            <Select
              options={Object.entries(strategyTypeLabels).map(([value, { label }]) => ({
                value,
                label,
              }))}
              disabled={!!editingId}
            />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="params" label="参数 (JSON)">
            <Input.TextArea rows={6} placeholder='{"buy_threshold": 0.3, "sell_threshold": -0.3}' />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
