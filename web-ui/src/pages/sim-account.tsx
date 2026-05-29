import { Typography } from "antd";
import styles from "./common.less";

const { Title, Paragraph } = Typography;

export default function SimAccountPage() {
  return (
    <div className={styles.pageContainer}>
      <Title level={2} className={styles.pageTitle}>模拟账户模块</Title>
      <Paragraph>
        用于模拟持仓、订单与盈亏统计；后端接口就绪后可在此接入完整交易流程。
      </Paragraph>
    </div>
  );
}
