import uuid
from app.models.document import Chunk

def text_splitter(chunk_size: int, overlap: int,document_id: uuid.UUID, pages: list  ):
    chunks_to_save = []
    step = chunk_size - overlap
    for page in pages:
        text = page.page_content
        page_num = page.metadata.get('page' , 0)
        
        cursor = 0



        while cursor < len(text):
            start_pos = cursor
            end_pos = min(cursor + chunk_size, len(text))

            if end_pos < len(text):
                last_space = text.rfind(" ", start_pos, end_pos)
                if last_space != -1:
                    end_pos = last_space
        
            content = text[start_pos:end_pos].strip()

            if content:
                chunk = Chunk(
                    doc_id=document_id,
                    content=content,
                    chunk_index=len(chunks_to_save),
                    page_num=page_num,
                    start_char=start_pos,
                    end_char=end_pos,
)
                chunks_to_save.append(chunk)
            cursor += step

           
    return chunks_to_save