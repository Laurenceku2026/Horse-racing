const express = require('express');
const cors = require('cors');
const { createClient } = require('@supabase/supabase-js');
const { HorseRacingAPI } = require('@gikndue/hkjc-api');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
const supabase = createClient(supabaseUrl, supabaseKey);
const horseAPI = new HorseRacingAPI();

app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.get('/api/meetings', async (req, res) => {
    try {
        const activeMeetings = await horseAPI.getActiveMeetings();
        res.json({ success: true, data: activeMeetings });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

app.post('/api/sync/race', async (req, res) => {
    const { date, venue, raceNo } = req.body;
    
    console.log(`[开始同步] ${date} ${venue} 第${raceNo}场`);
    
    try {
        const raceDetails = await horseAPI.getRaceWithDateAndVenueCode(date, venue, parseInt(raceNo));
        
        if (!raceDetails) {
            return res.json({ success: false, error: '未找到赛事数据' });
        }
        
        // 保存赛事
        await supabase.from('races').upsert({
            race_date: date,
            venue: venue,
            race_no: parseInt(raceNo),
            distance: raceDetails.distance || 0,
            total_runners: raceDetails.runners?.length || 0,
            race_status: 'RUNNERS'
        }, { onConflict: 'race_date,venue,race_no' });
        
        // 处理 runners
        const runners = raceDetails.runners || [];
        
        for (const runner of runners) {
            // 直接使用 runner.name_en
            const horseName = runner.name_en;
            const horseNo = parseInt(runner.no);
            const draw = parseInt(runner.barrierDrawNumber);
            const actualWeight = parseInt(runner.handicapWeight);
            const rating = parseInt(runner.internationalRating);
            const jockeyName = runner.jockey?.name_en;
            
            console.log(`保存马匹: ${horseName}, 档位: ${draw}, 骑师: ${jockeyName}`);
            
            // 保存马匹
            if (horseName) {
                await supabase.from('horses').upsert({
                    name_en: horseName,
                    name_zh: runner.name_ch || ''
                }, { onConflict: 'name_en' });
            }
            
            // 保存骑师
            if (jockeyName) {
                await supabase.from('jockeys').upsert({
                    name_en: jockeyName,
                    name_zh: runner.jockey?.name_ch || ''
                }, { onConflict: 'name_en' });
            }
            
            // 保存出赛记录
            await supabase.from('race_runners').upsert({
                race_date: date,
                race_no: parseInt(raceNo),
                venue: venue,
                horse_name: horseName,
                horse_no: horseNo,
                draw: draw,
                actual_weight: actualWeight,
                rating: rating,
                jockey_name: jockeyName
            }, { onConflict: 'race_date,venue,race_no,horse_no' });
        }
        
        console.log(`[同步完成] ${date} ${venue} 第${raceNo}场, ${runners.length} 匹马`);
        res.json({ success: true });
        
    } catch (error) {
        console.error('同步失败:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

app.listen(PORT, '0.0.0.0', () => {
    console.log(`HKJC API Server running on port ${PORT}`);
});
