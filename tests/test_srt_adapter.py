from otto_trans.adapter.srt import SRTAdapter, SRTBlock


SRT_SAMPLE = b"1\r\n00:00:01,000 --> 00:00:04,000\r\nHello, world!\r\n\r\n2\r\n00:00:05,000 --> 00:00:08,000\r\nThis is a test.\r\n"


def test_srt_extract():
    segments = SRTAdapter.extract(SRT_SAMPLE)
    assert len(segments) == 2
    assert segments[0].text == "Hello, world!"
    assert segments[1].text == "This is a test."
    assert isinstance(segments[0].context, SRTBlock)
    assert segments[0].context.seq == 1
    assert segments[0].context.start == "00:00:01,000"
    assert segments[0].context.end == "00:00:04,000"
    assert segments[1].context.seq == 2


def test_srt_reassemble():
    segments = SRTAdapter.extract(SRT_SAMPLE)
    segments[0].text = "你好，世界！"
    segments[1].text = "这是一个测试。"
    result = SRTAdapter.reassemble(SRT_SAMPLE, segments)
    text = result.decode("utf-8-sig")
    assert "你好，世界！" in text
    assert "这是一个测试。" in text
    assert "00:00:01,000" in text  # timestamps preserved
    assert "00:00:05,000" in text


def test_srt_extract_empty():
    segments = SRTAdapter.extract(b"")
    assert len(segments) == 0


def test_srt_roundtrip():
    """extract → modify → reassemble → extract 应保持结构"""
    segments = SRTAdapter.extract(SRT_SAMPLE)
    reassembled = SRTAdapter.reassemble(SRT_SAMPLE, segments)
    segments2 = SRTAdapter.extract(reassembled)
    assert len(segments2) == 2
    assert segments2[0].text == "Hello, world!"
    assert segments2[1].text == "This is a test."
