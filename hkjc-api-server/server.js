const express = require('express');
const cors = require('cors');
const { createClient } = require('@supabase/supabase-js');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

// 中间件
app.use(cors());
app.use(express.json());

// Supabase 客户端
const supabase = createClient(
    process.env.SUPABASE_URL,
    process.env.SUPABASE_SERVICE_ROLE_KEY
);

// ==================== 健康检查 ====================
app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// ==================== 模拟数据（暂时不用真实API） ====================
// 由于 @gikndue/hkjc-api 需要实际安装，我们先返回模拟数据测试部署
app.get('/api/meetings', (req, res) => {
    res.json({ 
        success: true, 
        data: [
            { date: '2024-12-15', venue: 'ST', raceCount: 10 },
            { date: '2024-12-18', venue: 'HV', raceCount: 8 }
        ]
    });
});

// 同步赛事接口
app.post('/api/sync/race', async (req, res) => {
    const { date, venue, raceNo } = req.body;
    
    console.log(`收到同步请求: ${date} ${venue} 第${raceNo}场`);
    
    // 模拟返回成功
    res.json({ 
        success: true, 
        message: `同步成功: ${date} ${venue} 第${raceNo}场`,
        data: { runners: 12 }
    });
});

// 批量同步
app.post('/api/sync/day', async (req, res) => {
    const { date } = req.body;
    
    res.json({ 
        success: true, 
        message: `同步完成: ${date}`,
        results: [{ raceNo: 1, success: true }, { raceNo: 2, success: true }]
    });
});

// 启动服务器
app.listen(PORT, '0.0.0.0', () => {
    console.log(`HKJC API Server running on port ${PORT}`);
});
