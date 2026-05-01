import pywencai
import pandas as pd
import os

def get_top_200_popularity():
    # 使用自然语言查询人气排名前200的股票
    query_text = "人气排名前200"
    
    try:
        # 调用pywencai.get方法，传入查询语句和Cookie
        df = pywencai.get(query=query_text, cookie='other_uid=Ths_iwencai_Xuangu_agsdg2irvmfxm1n8ky28tkie88jpcbek; cid=68427bc55522fae6a5111dbd92156a501777565240; _clck=6k8vpw%7C2%7Cg5o%7C0%7C0; u_ukey=A10702B8689642C6BE607730E11E6E4A; u_uver=1.0.0; u_dpass=7JtSi9YA7SmYS5Vll74m3DDNDkuM%2BVmwKzLJIaxbGUR9nqWYNhRDTmVwYwNuXuYtHi80LrSsTFH9a%2B6rtRvqGg%3D%3D; u_did=EA7ACB21D3BC466E954A0D9BD56D245A; u_ttype=WEB; user=MDrN7bCyQXVrOjpOb25lOjUwMDo1MjA4MDM2Mjg6NywxMTExMTExMTExMSw0MDs0NCwxMSw0MDs2LDEsNDA7NSwxLDQwOzEsMTAxLDQwOzIsMSw0MDszLDEsNDA7NSwxLDQwOzgsMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDEsNDA7MTAyLDEsNDA6MjQ6Ojo1MTA4MDM2Mjg6MTc3NzU5NjU0OTo6OjE1ODIxMTcwODA6NjA0ODAwOjA6MTVmZjJkNmZhZTFmY2EyYjQxY2Y2YTZhZjNhOGQ0ODY3OmRlZmF1bHRfNTox; userid=510803628; u_name=%CD%ED%B0%B2Auk; escapename=%25u665a%25u5b89Auk; ticket=3853d08a581e56d99ad8bc76ea12a284; user_status=0; utk=e1101f21d7eb93eb75b8c4ba406060e5; sess_tk=eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiIsImtpZCI6InNlc3NfdGtfMSIsImJ0eSI6InNlc3NfdGsifQ.eyJqdGkiOiI2NzQ4OGQzYWFmYTZmNjFjYjRhMmZjZTFmYWQ2ZjI1ZjEiLCJpYXQiOjE3Nzc1OTY1NDksImV4cCI6MTc3ODIwMTM0OSwic3ViIjoiNTEwODAzNjI4IiwiaXNzIjoidXBhc3MuaXdlbmNhaS5jb20iLCJhdWQiOiIyMDIwMTExODUyODg5MDcyIiwiYWN0Ijoib2ZjIiwiY3VocyI6IjM1NzdmMjRhYTNmYzA1ZTA5NGRlMjQwYTIzMzAxNDFkOTAzNzMwOTkzMzk0NjQxYWEzMDU5NDZmM2NmYTIyZDQifQ.GTiBk20n5-Hf6XHoPrWevfU5tkxkZFsmrt9eWFuSOP_zdfbgVSmZodA59JQbiR9CKw3K5McT7fG_rQMqB-P_Dg; cuc=70suo3g0cjfm; THSSESSID=98419724b8fd5da354cfb5678b; _clsk=2uamd6o5iiyf%7C1777596595955%7C7%7C1%7C; v=A0i3vhK3tZjIJdkcSl1BIrCKH71f8ayYjlWAfwL5lEO23ebjqgF8i95lUBpR', loop=True)
        
        if df is not None and not df.empty:
            print(f"成功获取到 {len(df)} 条数据")
            # 打印前几行看看效果
            print(df.head())
            
            old_file = '同花顺人气前200.csv'
            new_stocks_file = f'新增股票{pd.Timestamp.now().strftime("%Y-%m-%d %H-%M-%S")}.csv'
            
            if os.path.exists(old_file):
                old_df = pd.read_csv(old_file, encoding='utf-8-sig')
                
                if len(old_df.columns) > 0 and len(df.columns) > 0:
                    first_col_old = old_df.columns[0]
                    first_col_new = df.columns[0]
                    
                    old_stocks = set(old_df[first_col_old].astype(str))
                    new_stocks = set(df[first_col_new].astype(str))
                    
                    added_stocks = new_stocks - old_stocks
                    
                    if added_stocks:
                        added_df = df[df[first_col_new].astype(str).isin(added_stocks)]
                        added_df.to_csv(new_stocks_file, index=False, encoding='utf-8-sig')
                        print(f"发现 {len(added_stocks)} 只新增股票，已保存到 '{new_stocks_file}'")
                        print("新增股票列表：")
                        print(added_df)
                    else:
                        print("没有发现新增股票")
                else:
                    print("CSV文件格式异常，无法进行比较")
            else:
                print(f"'{old_file}' 不存在，将直接保存新数据")
            
            df.to_csv(old_file, index=False, encoding='utf-8-sig')
            print(f"最新数据已保存到 '{old_file}'")
        else:
            print("未获取到数据，请检查查询条件或Cookie是否有效。")
            
    except Exception as e:
        print(f"请求发生错误：{e}")

if __name__ == "__main__":
    get_top_200_popularity()